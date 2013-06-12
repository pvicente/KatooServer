'''
Created on Jun 12, 2013

@author: pvicente
'''
from katoo.data import GoogleUser
from twisted.application import service
from twisted.internet import defer, reactor
from twisted.python import log
from katoo.api import login

class Supervisor(service.Service):
    
    @property
    def name(self):
        return 'SUPERVISOR'
    
    @defer.inlineCallbacks
    def reconnectUsers(self):
        connected_users = yield GoogleUser.get_connected()
        for data in connected_users:
            try:
                user = GoogleUser(**data)
                yield login(user)
            except Exception as e:
                log.err('Exception %s reconnectin to user %s'%(e, data['_userid']))
    
    def startService(self):
        reactor.callLater(5, self.reconnectUsers)
        return service.Service.startService(self)
    