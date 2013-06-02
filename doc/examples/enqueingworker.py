'''
Created on May 28, 2013

@author: pvicente
'''
from katoo.utils.redis import RedisMixin
from twisted.application import service
from tworkerservice import TEnqueingService
import os

RedisMixin.setup()
application = service.Application("enqueingworker")

sleep_time = float(os.getenv('ENQUEUE_SLEEPTIME', 0.001))

worker = TEnqueingService('default', sleep_time)
worker.setServiceParent(application)