'''
Created on May 28, 2013

@author: pvicente
'''
from twisted.application import service
from katoo.rqtwisted import RedisMixin
from tworkerservice import TDequeingService

RedisMixin.setup()
application = service.Application("dequeingworker")

worker = TDequeingService('default', 1)
worker.setServiceParent(application)