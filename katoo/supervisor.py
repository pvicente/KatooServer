'''
Created on Jun 12, 2013

@author: pvicente
'''
from katoo import conf
from katoo.api import login
from katoo.data import GoogleUser
from twisted.application import service
from twisted.internet import defer, reactor
from twisted.internet.task import LoopingCall
from twisted.python import log
import cyclone.httpclient

class Supervisor(service.Service):
    
    @property
    def name(self):
        return 'SUPERVISOR'
    
    @defer.inlineCallbacks
    def avoidHerokuUnidling(self, url):
        yield cyclone.httpclient.fetch(url)
    
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
        if not conf.HEROKU_UNIDLING_URL is None:
            t = LoopingCall(self.avoidHerokuUnidling, conf.HEROKU_UNIDLING_URL)
            t.start(1800, now = True)
        reactor.callLater(5, self.reconnectUsers)
        return service.Service.startService(self)
    