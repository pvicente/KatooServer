'''
Created on May 28, 2013

@author: pvicente
'''
from katoo.utils.redis import RedisMixin
from twisted.application import service
from tworkerservice import TDequeingService
import os

RedisMixin.setup()
application = service.Application("dequeingworker")

blocking_seconds = int(os.getenv('DEQUEUE_BLOCKTIME', 1))
workers = int(os.getenv('DEQUEUE_WORKERS', 1))

for i in xrange(workers):
    t = TDequeingService('default', blocking_seconds)
    t.setServiceParent(application)
