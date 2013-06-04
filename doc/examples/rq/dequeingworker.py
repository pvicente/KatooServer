'''
Created on May 28, 2013

@author: pvicente
'''
from katoo.utils.connections import RedisMixin
from twisted.application import service
import os
from tworkerservice import TInlineDequeingService

RedisMixin.setup()
application = service.Application("dequeingworker")

blocking_seconds = int(os.getenv('DEQUEUE_BLOCKTIME', 1))
workers = int(os.getenv('DEQUEUE_WORKERS', 1))

for i in xrange(workers):
    t = TInlineDequeingService('default', blocking_seconds)
    t.setServiceParent(application)
