from coroweb import get
from models import User
import asyncio

@get('/')
async def index(request):
	users = await User.findAll()
	# 视图函数返回的值是dict
	return {
		# 在response_middleware中会搜索模板
		'__template__': 'test.html',
		# 传入模板的数据
		'users': users
	}

@get('/hello')
async def hello(request):
	return '<h1>hello!</h1>'

