'''
Created on Jun 12, 2013

@author: pvicente
'''
from katoo import conf
from katoo.api import API
from katoo.apns.api import sendcustom
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
        log.msg('RECONNECTING_USERS', len(connected_users))
        for data in connected_users:
            try:
                user = GoogleUser(**data)
                yield API(user.userid).login(user)
            except Exception as e:
                log.err('Exception %s reconnecting user %s'%(e, data['_userid']))
    
    @defer.inlineCallbacks
    def disconnectAwayUsers(self):
        away_users = yield GoogleUser.get_away()
        away_users  = [] if not away_users else away_users
        log.msg('PULLING_FROM_AWAY_USERS: %s'%(len(away_users)))
        for data in away_users:
            try:
                user = GoogleUser(**data)
                yield API(user.userid).disconnect(user.userid)
                yield sendcustom(lang=user.lang, token=user.pushtoken, badgenumber=user.badgenumber, type_msg='disconnect', sound='')
            except Exception as e:
                log.err('Exception %s disconnecting user %s'%(e, data['_userid']))
    
    def startService(self):
        if not conf.HEROKU_UNIDLING_URL is None:
            t = LoopingCall(self.avoidHerokuUnidling, conf.HEROKU_UNIDLING_URL)
            t.start(1800, now = True)
        t = LoopingCall(self.disconnectAwayUsers)
        t.start(conf.TASK_DISCONNECT_SECONDS, now = False)
        reactor.callLater(conf.TWISTED_WARMUP, self.reconnectUsers)
        return service.Service.startService(self)
    