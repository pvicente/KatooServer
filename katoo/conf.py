'''
Created on May 29, 2013

@author: pvicente
'''
import os

##REDIS_CONNECTION_MANAGEMENT
REDIS_URL=os.getenv('REDISCLOUD_URL', 'redis://localhost:6379')
REDIS_POOL=int(os.getenv('REDIS_POOL', 10))

