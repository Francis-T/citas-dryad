import logging

class CustomLogging():
	def __init__(self, source):
		self.logger = logging.getLogger(source)

	def setup(self):
		self.logger.setLevel(logging.DEBUG)

		# console handler
		ch = logging.StreamHandler()
		ch.setLevel(logging.DEBUG)
	
		# file handler
		fh = logging.FileHandler("cache_node.log")

		# formatter
		formatter = logging.Formatter("%(asctime)s - [%(levelname)s] [%(threadName)s] (%(module)s:%(lineno)d) %(message)s") 
 
		# ch setting
		ch.setFormatter(formatter)
		self.logger.addHandler(ch)   

		# fh setting
		fh.setFormatter(formatter)
		self.logger.addHandler(fh)
		
		return self.logger	

