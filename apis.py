
class Page(object):
	def __init__(self, item_count, page_index=1, page_size=10):	
		self.item_count = item_count
		self.page_size = page_size
		# 计算blog总页数
		self.page_count = item_count // page_size + \
							(1 if item_count % page_size > 0 else 0)
		if (item_count == 0) or (page_index > self.page_count):
			self.offset = 0
			self.limit = 0
			self.page_index = 1
		else:
			self.page_index = page_index
			# 本页前的blog数量
			self.offset = self.page_size * (page_index - 1)
			self.limit = self.page_size
		self.has_next = self.page_index < self.page_count
		self.has_previous = self.page_index > 1

	def __str__(self):
		return 'item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset: %s, limit: %s' % \
					(self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

	__repr__ = __str__


class APIError(Exception):
	'''
	APIError基类， 包含错误类型（必要），数据（可选），信息（可选）
	'''	
	def __init__(self, error, data = '', message = ''):
		super(APIError, self).__init__(message)
		self.error = error
		self.data = data
		self.message = message

class APIValueError(APIError):
	'''
	数据输入有问题，data说明输入的错误字段
	'''
	def __init__(self, field, message = ''):
		super(APIValueError, self).__init__('Value: invalid', field, message)

class APIResourceNotfoundError(APIError):
	# 找不到资源
	def __init__(self, field, message = ''):
		super(APIResourceNotfoundError,self).__init__('Value: Notfound', field, message)

class APIPermissionError(APIError):
	# 没有接口权限
	def __init__(self, message = ''):
		super(APIPermissionError, self).__init__('Permission: forbidden', 'Permission', message)

