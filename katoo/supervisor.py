'''
Created on Jun 12, 2013

@author: pvicente
'''
from katoo import conf
from katoo.apns.api import API as APNSAPI
from katoo.api import API
from katoo.data import GoogleUser
from twisted.application import service
from twisted.internet import defer, reactor
from twisted.internet.task import LoopingCall
import cyclone.httpclient
from katoo.utils.applog import getLogger, getLoggerAdapter

log = getLogger(__name__, level='INFO')

class Supervisor(service.Service):
    log = getLoggerAdapter(log, id='SUPERVISOR-%s'%(conf.MACHINEID))
    
    @property
    def name(self):
        return 'SUPERVISOR'
    
    @defer.inlineCallbacks
    def avoidHerokuUnidling(self, url):
        self.log.info('AVOIDING HEROKU IDLING: %s', url)
        yield cyclone.httpclient.fetch(url)
    
    @defer.inlineCallbacks
    def reconnectUsers(self):
        connected_users = yield GoogleUser.get_connected()
        self.log.info('RECONNECTING_USERS: %s', len(connected_users))
        for data in connected_users:
            try:
                user = GoogleUser(**data)
                yield API(user.userid).login(user)
            except Exception as e:
                self.log.error('Exception %s reconnecting user %s', e, data['_userid'])
    
    @defer.inlineCallbacks
    def disconnectAwayUsers(self):
        away_users = yield GoogleUser.get_away()
        away_users  = [] if not away_users else away_users
        self.log.info('CHECKING_AWAY_USERS: %s', len(away_users))
        for data in away_users:
            try:
                user = GoogleUser(**data)
                yield API(user.userid).disconnect(user.userid)
                yield APNSAPI(user.userid).sendcustom(lang=user.lang, token=user.pushtoken, badgenumber=user.badgenumber, type_msg='disconnect', sound='')
            except Exception as e:
                self.log.error('Exception %s disconnecting user %s', e, data['_userid'])
    
    def startService(self):
        if not conf.HEROKU_UNIDLING_URL is None:
            t = LoopingCall(self.avoidHerokuUnidling, conf.HEROKU_UNIDLING_URL)
            t.start(1800, now = True)
        t = LoopingCall(self.disconnectAwayUsers)
        t.start(conf.TASK_DISCONNECT_SECONDS, now = False)
        reactor.callLater(conf.TWISTED_WARMUP, self.reconnectUsers)
        return service.Service.startService(self)
    