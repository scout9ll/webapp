import orm, asyncio
from models import User, Blog, Comment

loop = asyncio.get_event_loop()
async def test():
	await orm.create_pool(loop, user='root', password='password', db='awesome')
	u = User(name='Test', email='422925090@qq.com', passwd='123456', image='about:blank')
	await u.save()


loop.run_until_complete(test())
loop.close()
