'''
Created on May 29, 2013

@author: pvicente
'''
import os

#WEBSERVICE
PORT=int(os.getenv('PORT', 5000))
LISTEN=os.getenv('LISTEN', '0.0.0.0')

##REDIS_CONNECTION_MANAGEMENT
REDIS_URL=os.getenv('REDISCLOUD_URL', 'redis://localhost:6379')
REDIS_POOL=int(os.getenv('REDIS_POOL', 10))

#MONGO
MONGO_URL=os.getenv('MONGOLAB_URI', 'mongo://localhost:27017')
MONGO_POOL=int(os.getenv('MONGO_POOL', 10))

