from models import User, Blog, Comment, next_id
from coroweb import get, post
from aiohttp import web
from config import configs
from apis import APIError, APIValueError, APIPermissionError, APIResourceNotfoundError, Page
import asyncio, time, re, hashlib, json, logging, markdown2
logging.basicConfig(level=logging.INFO)


COOKIE_NAME = 'awesession' 
_COOKIE_KEY = configs['session']['secret']

_RE_EMAIL = re.compile(r'^[a-zA-Z0-9\.\-\_]+\@[a-zA-Z0-9\-\_]+(\.[a-zA-Z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


# 根据user对象和有效时间，生成cookie值
def user2cookie(user, max_age):
	# id-到期时间-摘要算法
	expires = str(time.time()+max_age)
	s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
	L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
	'''hash = hashlib.sha1(str.encode('utf-8'))
	   hash.hexdigest()'''	
	return '-'.join(L)

async def cookie2user(cookie_str):
	if not cookie_str: # 若cookie不存在
		return None
	try:
		L = cookie_str.split('-')
		if len(L) != 3:
			return None
		uid, expires, sha1 = L
		# 若cookie过期
		if float(expires) < time.time():
			return None
		user = await User.find(uid)
		# 若用户不存在
		if not user:
			return None
		# 用数据库中user信息生成sha1和cookie中的比较
		s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
		if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
			logging.info('Invalid sha1')
			return None
		# 覆盖user的passwd字段
		user.passwd = '******'
		return user
	except Exception as e:
		logging.exception(e)
		return None		

def get_page_index(page_str):
	p = 1
	try:
		p = int(page_str)
	except ValueError as e:
		pass
	if p < 1:
		p = 1
	return p

def text2html(text):
	# HTML转义字符
	# "				&quot;
	# & 			&amp;
	# < 			&lt;
	# > 			&gt;
	# 不断开空格	&nbsp;
	# text先经filter处理，只留下不为空的数据，list形式。
	# 再由map函数，每段text经lambda处理，将text转义为html语言
	lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
	return ''.join(lines)
# -------------------------------------------------------用户浏览页面----------------------------------------------------------------
# 主页
@get('/')
async def index(request, *, page='1'):
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	page = Page(num, page_index)
	if num == 0:
		blogs = []
	else:
		blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
	return {
		'__template__': 'blogs.html',
		'page': page,
		'blogs': blogs,
		'__user__': request.__user__
	}
# 注册页面
@get('/register')
def register():
	return { '__template__': 'register.html'}

# 登录页面
@get('/signin')
def signin():
	return {
		'__template__': 'signin.html'
	}

# 登出
@get('/signout')
def signout(request):
	referer = request.headers.get('Referer')
	r = web.HTTPFound(referer or '/')
	#清理cookie
	r.set_cookie(COOKIE_NAME, '-deleted-', max_age = 0, httponly = True)
	logging.info('user signed out')
	return r

@get('/blog/{id}')
async def get_blog(id, request):
	blog = await Blog.find(id)
	comments = await Comment.findAll('blog_id=?', [id], orderBy='creat_at desc')
	for c in comments:
		c.html_content = text2html(c.content)
	blog.html_content = markdown2.markdown(blog.content)
	return {
		'__template__': 'blog.html',
		'blog': blog,
		'comments': comments,
		'__user__': request.__user__
	}
# -------------------------------------------------------管理页面----------------------------------------------------------------

#评论列表
@get('/manage/comments')
def manage_comments(request, *, page='1'):
	return {
		'__template__': 'manage_comments.html',
		'page_index': get_page_index(page),
		'__user__': request.__user__
	}

# 日志列表
@get('/manage/blogs')
def manage_blogs(request, *, page='1'):
	return {
		'__template__': 'manage_blogs.html',
		'page_index': get_page_index(page),
		'__user__': request.__user__
	}

# 创建日志
@get('/manage/blogs/create')
def manage_create_blog(request):
	return {
		'__template__': 'manage_blog_edit.html',
		'id': '',
		'action': '/api/blogs',
		'__user__': request.__user__
	}

# 日志列表
@get('/manage/users')
def manage_users(request, *, page='1'):
	return {
		'__template__': 'manage_users.html',
		'page_index': get_page_index(page),
		'__user__': request.__user__
	}


# 修改日志
@get('/manage/blogs/edit')
async def manage_edit_blog(request, *, id):
	return {
		'__template__': 'manage_blog_edit.html',
		'id': id,
		'action': '/api/blogs/%s' % id,
		'__user__': request.__user__
	}

# -------------------------------------------------------后端API----------------------------------------------------------------

# 获取日志：用于管理日志页面
@get('/api/blogs')
async def api_blogs(*, page=1):
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	# 建立Page类分页
	p = Page(item_count=num, page_index=page_index)
	if num == 0:
		return dict(page = p, blogs=())
	blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page = p, blogs=blogs)

# 创建日志：用于创建日志页面
@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
	check_damin(request)
	if not name or not name.strip():
		raise APIValueError('name', "Name can't be empty.")
	if not summary or not summary.strip():
		raise APIValueError('Summary', "Summary can't be empty.")
	if not content or not content.strip():
		raise APIValueError('content', "Content can't be empty.")
	blog = Blog(
		user_id = request.__user__.id,
		user_name = request.__user__.name,
		user_image = request.__user__.image,
		name = name.strip(),
		summary = summary.strip(),
		content = content.strip()
	)
	await blog.save()
	return blog


@get('/api/blogs/{id}')
async def api_get_blog(*, id):
	blog = await Blog.find(id)
	return blog

# 修改日志：用于修改日志页面
@post('/api/blogs/{id}')
async def api_update_blog(id, request, *, name, summary, content):
	check_damin(request)
	blog = await Blog.find(id)
	if not name or not name.strip():
		raise APIValueError('name', "Name can't be empty.")
	if not summary or not summary.strip():
		raise APIValueError('Summary', "Summary can't be empty.")
	if not content or not content.strip():
		raise APIValueError('content', "Content can't be empty.")
	blog.name = name.strip()
	blog.summary = summary.strip()
	blog.content = content.strip()
	await blog.update()
	return blog

# 删除日志
@post('/api/blogs/{id}/delete')
async def api_delete_blog(id, request):
	check_damin(request)
	blog = await Blog.find(id)
	await blog.remove()
	return dict(id=id)

# 获取评论：用于评论管理页面
@get('/api/comments')
async def api_comments(*, page=1):
	page_index = get_page_index(page)
	num = await Comment.findNumber('count(id)')
	# 建立Page类分页
	p = Page(item_count=num, page_index=page_index)
	if num == 0:
		return dict(page = p, comments=())
	comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page = p, comments=comments)

#创建评论
@post('/api/blogs/{id}/comments')
async def api_create_comment(id, request, *, content):
	user = request.__user__ # 检查登录
	if user is None:
		raise APIPermissionError('Please signin first.')
	if not content or not content.strip():
		raise APIValueError('content', "Content can't be empty.")
	blog = await Blog.find(id)
	if blog is None:
		raise APIValueError('Blog')
	comment = Comment(
		user_id = user.id,
		user_name = user.name,
		user_image = user.image,
		blog_id = blog.id,
		content = content.strip()
	)
	await comment.save()
	return comment	

# 删除评论
@post('/api/comments/{id}/delete')
async def api_delete_comment(id, request):
	check_damin(request)
	comment = await Comment.find(id)
	if comment is None:
		raise APIResourceNotfoundError('comment')
	await comment.remove()
	return dict(id=id)

@get('/api/users')
async def api_users(*, page=1):
	page_index = get_page_index(page)
	num = await User.findNumber('count(id)')
	# 建立Page类分页
	p = Page(item_count=num, page_index=page_index)
	if num == 0:
		return dict(page = p, users=())
	users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page = p, users=users)


# 用户注册
@post('/api/users')
async def api_register_user(*, name, email, passwd):
	if not name or not name.strip():
		raise APIValueError('name')
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd')
	users = await User.findAll('email=?', [email])
	# 判断邮箱是否已被注册
	if len(users)>0:
		raise APIError('register: failed', 'email', 'Email is already in use.')
	# 计算密码SHA1散列值需要用到uid，故手动调用next_id
	uid = next_id()
	# 数据库保存uid+密码的SHA1散列值数据
	sha1_passwd = '%s:%s' % (uid, passwd)
	user = User(
		id=uid, 
		name=name.strip(), 
		email=email, 
		passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
		# Gravatar是一个第三方头像服务商，能把头像和邮件地址相关联。用户可以到http://www.gravatar.com注册并上传头像。
		# 也可以通过直接在http://www.gravatar.com/avatar/地址后面加上邮箱的MD5散列值获取默认头像。
		image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest()
	)
	await user.save()
	# 制作cookie返回
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******' # 在上下文环境中掩盖user对象的passwd字段，并不影响数据库中passwd字段
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r

# 用户登录
@post('/api/authenticate')
async def authenticate(*, email, passwd):
	if not email:
		raise APIValueError('email', 'Invalid email.')
	if not passwd:
		raise APIValueError('passwd', 'Invalid password.')
	users = await User.findAll('email=?', [email])
	if len(users) == 0:
		raise APIValueError('email', 'Emial not exist.')
	user = users[0] # findAll返回的是仅含一个user对象的list
	# 把用户输入的密码进行摘要算法
	sha1_passwd = '%s:%s' % (user.id, passwd)
	# 与数据库中密码进行比较
	if hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest() != user.passwd:
		raise APIValueError('passwd', 'Invalid password.')
	# 重置cookie，返回给客户端
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******' 
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r	

# 检查是否登录且为管理员
def check_damin(request):
	if request.__user__ is None or not request.__user__.admin:
		raise APIPermissionError()




