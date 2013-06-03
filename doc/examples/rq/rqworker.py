'''
Created on Jun 3, 2013

@author: pvicente
'''
from katoo.utils.redis import RedisMixin
from katoo.rqtwisted.worker import Worker
from twisted.application import service
import os

RedisMixin.setup()
application = service.Application("dequeingworker")

blocking_seconds = int(os.getenv('DEQUEUE_BLOCKTIME', 1))
workers = int(os.getenv('WORKERS', 1))

for i in xrange(workers):
    t = Worker(['default'])
    t.setServiceParent(application)