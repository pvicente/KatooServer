'''
Created on May 28, 2013

@author: pvicente
'''
from twisted.application import service
from katoo.rqtwisted import RedisMixin
from tworkerservice import TEnqueingService

RedisMixin.setup()
application = service.Application("enqueingworker")

worker = TEnqueingService('default', 0.0001)
worker.setServiceParent(application)