
# 定义Feild基类，负责保存db表的字段名和字段类型


class Field(object):
	def __init__(self, name, column_type, primary_key, default):
		# 表的字段包含名字、类型、是否为主键和默认值
		self.name = name
		self.column_type = column_type
		self.primary_key = primary_key
		self.default = default

	# 输出数据表的信息：类名，字段类型，名字
	def __str__(self):
		return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

#不同类型的字段类型，使用不同Feild子类
#一个子类，对象表的一个列
class StringField(Field):
	def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(255)'):
		super(StringField, self).__init__(name, ddl, primary_key, default)

class IntegerField(Field):
	def __init__(self, name=None, primary_key=False, default=0):
		super(IntegerField, self).__init__(name, 'bigint', primary_key, default)

class BooleanField(Field):
	def __init__(self, name=None, default=False):
		super(BooleanField, self).__init__(name, 'bollean', False, default)

class TextField(Field):
	def __init__(self, name=None, default=None):
		super(TextField, self).__init__(name, 'Text', False, default)

class FloatField(Field):
	def __init__(self, name=None, primary_key=False, default=None):
		super(FloatField, self).__init__(name, 'real', primary_key, default)