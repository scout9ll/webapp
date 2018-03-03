import aiomysql, asyncio, logging
from fields import Field
logging.basicConfig(level=logging.INFO)



# SQL语句反馈
def log(sql, args=()):
	logging.info('SQL: %s, %s' % (sql, args))

# 创建一个全局连接池
async def create_pool(loop, **kw):
	logging.info('create database connection pool...')
	global __pool
	__pool = await aiomysql.create_pool(
		host = kw.get('host', 'localhost'),
		port = kw.get('port', 3306),
		user = kw['user'],
		password = kw['password'],
		db = kw['db'],
		charset = kw.get('charset', 'utf8'),
		autocommit = kw.get('autocommit', True),
		maxsize = kw.get('maxsize', 10),
		minsize = kw.get('minsize', 1),
		loop = loop)

# 单独封装select
async def select(sql, args, size=None):
	log(sql, args)
	global __pool
	async with __pool.get() as conn:  # 或--> with await __pool as conn:
		# 创建一个DictCursor类指针，返回dict形式的结果集
		async with conn.cursor(aiomysql.DictCursor) as cur:
		# SQL语句占位符为?，MySQL为%s。
			await cur.execute(sql.replace('?', "%s"), args or ())
			if size:
				rs = await cur.fetchmany(size)
			else:
				rs = await cur.fetchall()
	logging.info('rows returned: %s' % len(rs))
	return rs

# 封装insert，update，delete
async def execute(sql, args, autocommit=True):
	log(sql, args)
	with await __pool as conn:
		if not autocommit:
			await conn.begin()
		try:
			async with conn.cursor(aiomysql.DictCursor) as cur:
				await cur.execute(sql.replace('?', "%s"), args)
				affected = cur.rowcount
			if not autocommit:
				await conn.commit()
		except BaseException as e:
			if not autocommit:
				await conn.rollback()
			raise e
		return affected

# 创建占位符，用于insert，updae，delete语句
def create_args_string(num):
	L = []
	for i in range(num):
		L.append('?')
	return ','.join(L)	


#定义Metaclass元类
class ModelMetaclass(type):
	def __new__(cls, name, bases, attrs):
		# 排除对Model基类的改动，只作用于Model的子类（数据库表）
		if name == 'Model':
			return type.__new__(cls, name, bases, attrs)
		tableName = attrs.get('__table__', None) or name
		logging.info('found model: %s (table: %s)' % (name, tableName))
		# 保存当前类属性名和Field字段的映射关系
		mappings = dict()
		# 保存除主键外的属性名
		fields = []
		primarykey = None
		for k, v in attrs.items():
			# 找到Field类型字段
			if isinstance(v, Field):
				logging.info('found mapping: %s ==> %s' % (k, v))
				mappings[k] = v
				# 若字段primary_key为True
				if v.primary_key:
					# 判断主键是否已被赋值
					if primarykey:
						raise BaseException('Duplicate primary key for field: %s' % k)
					primarykey = k
				else:
					fields.append(k)
		if not primarykey:
			raise BaseException('primary key not found')
		# 删除类中的属性，因为会和类的实例同名属性冲突
		for k in mappings.keys():
			attrs.pop(k)
		#保存除主键外的属性名为``（输出字符串）的列表形式
		escaped_fields = list(map(lambda f: '`%s`' % f, fields))
		# 映射关系，表名，字段名，主键名
		# 将属性名和Field字段保存到类的__mappings__属性中
		attrs['__mappings__'] = mappings
		attrs['__table__'] = tableName
		attrs['__fields__'] = fields
		attrs['__primary_key__'] = primarykey
		#构造默认的SQL语句
		#反引号··功能同repr()，输出机器阅读语言
		attrs['__select__'] = 'select `%s`, %s from `%s`' % (primarykey, ','.join(escaped_fields), tableName)
		attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ','.join(escaped_fields), primarykey, create_args_string(len(escaped_fields)+1))
		attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ','.join(map(lambda f:'`%s`=?' % (mappings.get(f).name or f), fields)), primarykey)
		attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primarykey)
		return type.__new__(cls, name, bases, attrs)

class Model(dict, metaclass = ModelMetaclass):
	def __init__(self, **kw):
		super(Model, self).__init__(self, **kw)
	
	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError('Model object has no attribute: %s' % key)

	def __setattr__(self, key, value):
		self[key] = value

	def getValue(self, key):
		# 继承父类dict的内建函数getattr()
		return getattr(self, key, None)

	def getValueOrDefault(self, key):
		value = getattr(self, key, None)
		if not value:
			field = self.__mappings__[key]
			if field.default is not None:
				#default值可以设置为值或调用对象（无法设置值时，如default = time.time 插入当前时间）
				value = field.default() if callable(field.default) else field.default
				logging.debug('use default value for %s: %s' % (key, str(value)))
		return value

	# 类方法有类变量cls传入，从而可以用cls做一些相关的处理。
	# 有子类继承时，调用该类方法时，传入的类变量cls是子类，而非父类。 
	@classmethod
	async def findAll(cls, where=None, args=None, **kw):
		if not args:
			args = []
		sql = [cls.__select__] 
		if where: 
			sql.append('where')
			sql.append(where)
		orderBy = kw.get('orderBy', None)
		if orderBy:
			sql.append('order by')
			sql.append(orderBy)
		limit = kw.get('limit', None)
		if limit:
			sql.append('limit')
			if isinstance(limit, int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit, tuple) and len(limit)==2:
				sql.append('?, ?')
				args.extend(limit)
			else:
				raise('Invalid limit value: %s' % str(limit))
		rs = await select(' '.join(sql), args)	
		# 将返回的结果迭代生成类的实例，返回的都是实例对象, 而非仅仅是数据
		return [cls(**r) for r in rs] 

	@classmethod
	async def find(cls,primarykey):#根据主键查找数据库
		sql = '%s where `%s`=?' % (cls.__select__, cls.__primary_key__)
		rs = await select(sql, [primarykey], 1)
		if len(rs) == 0:
			return None
		return cls(**rs[0])

	@classmethod
	async def findNumber(cls, selectField, where=None, args=None):
		# 使用了SQL的聚集函数 count()
		# select %s as __num__ from table ==> __num__表示列的别名，筛选结果列名会变成__num__
		sql = ['select %s __num__ from `%s`' % (selectField, cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
		rs = await select(' '.join(sql), args, 1)
		if len(rs) == 0:
			return None
		# fetchmany()返回列表结果，用索引取出。又因为Dictcursor，值用key取出。
		return rs[0]['__num__']

	async def save(self):
		args = list(map(self.getValueOrDefault, self.__fields__))
		primarykey = self.getValueOrDefault(self.__primary_key__)
		args.append(primarykey)
		rows = await execute(self.__insert__, args)
		if rows != 1:
			logging.warn('failed to insert record: affected rows: %s' % rows)

	async def update(self):
		args = list(map(self.getValue, self.__fields__))
		primarykey = self.getValue(self.__primary_key__)
		args.append(primarykey)
		rows = await execute(self.__update__, args)
		if rows != 1:
			logging.warn('failed to update record: affected rows: %s' % rows)

	async def remove(self):
		args = [self.getValue(self.__primary_key__)]
		rows = await execute(self.__delete__, args)
		if rows != 1:
			logging.warn('failed to remove by primary key: affected rows: %s' % rows) 




















