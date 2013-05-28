'''
Created on May 27, 2013

@author: pvicente
'''
from twisted.application import service
from katoo.rqtwisted import RedisMixin
from katoo.tworkerservice import TQueuesService

RedisMixin.setup()
application = service.Application("twistedrqworker")

worker = TQueuesService(['default',])
worker.setServiceParent(application)
