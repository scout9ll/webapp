import config_default

# 整合config_default和config_override中的配置值
def merge(default, override):
	r = dict()
	for k, v in default.items():
		if k in override:
			if isinstance(v, dict):
				r[k] = merge(v, override[k])  # 若v是dict，继续迭代
			else:
				r[k] = override[k] # 否则，用新值覆盖默认值
		else:
			r[k] = v # 覆盖参数未定义时，仍使用默认参数
	return r

try:
	import config_override
	configs = merge(config_default.configs, config_override.configs)
except ImportError:
	pass
