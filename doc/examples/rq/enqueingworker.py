'''
Created on May 28, 2013

@author: pvicente
'''
from katoo.utils.connections import RedisMixin
from twisted.application import service
from tworkerservice import TEnqueingService
import os

RedisMixin.setup()
application = service.Application("enqueingworker")

sleep_time = float(os.getenv('ENQUEUE_SLEEPTIME', 0.001))
workers = int(os.getenv('ENQUEUE_WORKERS', 1))
for i in xrange(workers):
    TEnqueingService('default', sleep_time).setServiceParent(application)
