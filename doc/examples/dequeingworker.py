'''
Created on May 28, 2013

@author: pvicente
'''
from twisted.application import service
from katoo.rqtwisted import RedisMixin
from tworkerservice import TDequeingService

RedisMixin.setup()
application = service.Application("dequeingworker")

worker1 = TDequeingService('default', 1)
worker1.setServiceParent(application)
worker2 = TDequeingService('default', 1)
worker2.setServiceParent(application)
worker3 = TDequeingService('default', 1)
worker3.setServiceParent(application)
worker4 = TDequeingService('default', 1)
worker4.setServiceParent(application)