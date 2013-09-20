'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import conf, KatooApp
from katoo.apns.api import API
from katoo.data import GoogleMessage, GoogleRosterItem
from katoo.metrics import IncrementMetric, Metric
from katoo.utils.patterns import Observer
from katoo.utils.time import Timer
from twisted.internet import defer
from twisted.words.protocols.jabber import jid
from wokkel_extensions import ReauthXMPPClient
from xmppprotocol import CompleteBotProtocol, GenericXMPPHandler
import cyclone.httpclient
import json
import translate
import urllib

METRIC_SOURCE='XMPPGOOGLE'
METRIC_UNIT='events'

class RosterManager(object):
    ROSTER_IN_MEMORY=conf.XMPP_ROSTER_IN_MEMORY
    def __init__(self, userid, log):
        self._userid = userid
        self._roster = {}
        self.log = log
    
    @staticmethod
    def getName(roster_item):
        fromjid = getattr(roster_item, 'jid', None)
        defaultName = fromjid.user if isinstance(fromjid, jid.JID) else fromjid
        name = getattr(roster_item, 'name', '')
        name = name if name else defaultName
        return fromjid, name
    
    @defer.inlineCallbacks
    def processRoster(self, roster):
        for v in roster.itervalues():
            jid, name = self.getName(v)
            if name:
                yield self.set(jid,name=name)
    
    def _getBareJid(self, key):
        if isinstance(key, jid.JID):
            return key.userhost()
        else:
            return key
    
    @IncrementMetric(name='rostermanager_get', unit='calls', source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def get(self, key, default=None):
        barejid = self._getBareJid(key)
        if self.ROSTER_IN_MEMORY:
            defer.returnValue(self._roster.get(barejid, default))
        
        ret = yield GoogleRosterItem.load(self._userid, barejid)
        defer.returnValue(default if ret is None else ret)
    
    @IncrementMetric(name='rostermanager_set', unit='calls', source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def set(self, key, **kwargs):
        barejid = self._getBareJid(key)
        item = yield self.get(barejid)
        if item is None:
            item = GoogleRosterItem(self._userid, barejid)
        item.update(**kwargs)
        if self.ROSTER_IN_MEMORY:
            self._roster[barejid] = item
        else:
            yield item.save()
        defer.returnValue(None)
    
class GoogleHandler(GenericXMPPHandler):
    CONNECTIONS_METRIC=Metric(name='connections', value=None, unit='connections', source=METRIC_SOURCE, reset=False)
    CONNECTION_TIME_METRIC=Metric(name='connection_time', value=None, unit='seconds', source=METRIC_SOURCE, sampling=True)
    CONNECTION_KEEP_ALIVE_TIME_METRIC=Metric(name='connection_last_time_keep_alive', value=None, unit='seconds', source=METRIC_SOURCE, sampling=True)
    
    def __init__(self, client):
        GenericXMPPHandler.__init__(self, client)
        self.user = client.user
        self.roster = RosterManager(self.user.userid, self.log)
        self.connectionTime = None
    
    def isOwnBareJid(self, jid):
        return self.client.jid.user == jid.user and self.client.jid.host == jid.host
    
    @IncrementMetric(name='connection_established', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onConnectionEstablished(self):
        self.CONNECTIONS_METRIC.add(1)
        self.connectionTime = None
        self.log.info('CONNECTION_ESTABLISHED %s', self.user.jid)
    
    @IncrementMetric(name='connection_lost', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onConnectionLost(self, reason):
        self.CONNECTIONS_METRIC.add(-1)
        currTime = Timer().utcnow()
        connectedTime = 0 if self.connectionTime is None else (currTime - self.connectionTime).seconds
        lastTimeKeepAlive = (currTime - KatooApp().getService('XMPP_KEEPALIVE_SUPERVISOR').lastTime).seconds
        isAuthenticating = self.client.isAuthenticating()
        
        self.log.info('CONNECTION_LOST %s. Connected Time: %s. LastTimeKeepAlive: %s. Authenticating: %s. Reason %s',
                      self.user.jid, connectedTime, lastTimeKeepAlive, isAuthenticating, str(reason))
        self.CONNECTION_TIME_METRIC.add(connectedTime)
        self.CONNECTION_KEEP_ALIVE_TIME_METRIC.add(lastTimeKeepAlive)
        
        if not isAuthenticating:
            if connectedTime < conf.XMPP_MIN_CONNECTED_TIME:
                self.client.retries += 1
                if self.client.retries >= conf.XMPP_MAX_RETRIES:
                    self.client.onMaxRetries()
                    return
            else:
                self.client.retries = 0
    
    @IncrementMetric(name='connection_authenticated', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onAuthenticated(self):
        self.connectionTime = Timer().utcnow()
        self.log.info('CONNECTION_AUTHENTICATED %s', self.user.jid)
        
        #Set away state to be restored with right value when presences will be received
        self.user.away = True
        self.user.save()
        
        #Send Available and getting roster
        self.protocol.available(show=conf.XMPP_STATE, priority=conf.XMPP_PRIORITY, statuses={'en-US': conf.XMPP_MOOD} if conf.XMPP_MOOD else None)
        d = self.protocol.getRoster()
        d.addCallback(self.protocol.onRosterReceived)
        
    
    @IncrementMetric(name='presence_available', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onAvailableReceived(self, jid):
        if self.isOwnBareJid(jid) and jid.resource == self.user.resource:
            self.log.info('APP_GO_ONLINE %s',self.user.jid)
            self.user.away = False
            return self.user.save()
        self.log.debug('XMPP_GO_ONLINE %s <- %s@%s/%r', self.user.jid, jid.user, jid.host, jid.resource)
    
    @IncrementMetric(name='presence_unavailable', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onUnavailableReceived(self, jid):
        if self.isOwnBareJid(jid) and jid.resource == self.user.resource:
            self.log.info('APP_GO_AWAY %s', self.user.jid)
            self.user.away = True
            return self.user.save()
        self.log.debug('XMPP_GO_OFFLINE %s <- %s@%s/%r', self.user.jid, jid.user, jid.host, jid.resource)
    
    @IncrementMetric(name='roster_received', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def onRosterReceived(self, roster):
        yield self.roster.processRoster(roster)
        
        if not self.user.connected:
            #Remove data due to user is disconnected while processing is performed
            yield GoogleRosterItem.remove(self.user.userid)
        
        self.log.info('ROSTER_RECEIVED. PROCESSED ROSTER %s', self.user.jid)
    
    @IncrementMetric(name='roster_set', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onRosterSet(self, item):
        self.log.info('onRosterSet to %s <- item %s', self.user.jid, item)
        fromjid, name = self.roster.getName(item)
        if name:
            self.roster.set(fromjid, name=name)
    
    @IncrementMetric(name='roster_remove', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onRosterRemove(self, item):
        #We don't remove roster items
        self.log.info('onRosterRemove to %s <- item %s', self.user.jid, item)
    
    @IncrementMetric(name='message_received', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def onMessageReceived(self, fromjid, msgid, body):
        self.log.debug("MESSAGE_RECEIVED to %s. msgid(%s) from(%s): %r", self.user.jid, msgid, fromjid, body)
        barefromjid=fromjid.userhost()
        message = GoogleMessage(userid=self.user.userid, fromid=barefromjid, msgid=msgid, data=body)
        try:
            yield message.save()
            if self.user.pushtoken and self.user.away:
                roster_item = yield self.roster.get(barefromjid)
                if roster_item is None:
                    roster_item = GoogleRosterItem(_userid=self.user.userid, _jid=barefromjid)
                    roster_item.name = fromjid.user
                    #Set in roster to retrieve later
                    yield self.roster.set(fromjid, name=roster_item.name)
                
                self.user.badgenumber += 1
                self.log.debug('SENDING_PUSH %s. RosterItem: %s, User data: %s', self.user.jid, roster_item, self.user)
                yield API(self.user.userid).sendchatmessage(msg=body, token=self.user.pushtoken, badgenumber=self.user.badgenumber, jid=roster_item.jid, fullname=roster_item.contactName, 
                                                            sound=self.user.favoritesound if roster_item.favorite else self.user.pushsound, favorite=roster_item.favorite, lang=self.user.lang)
                self.log.debug('PUSH SENT %s', self.user.jid)
                yield self.user.save()
        except Exception as e:
            self.log.err(e, 'ON_MESSAGE_RECEIVED_EXCEPTION')
    
class XMPPGoogle(ReauthXMPPClient, Observer):
    def __init__(self, user, app):
        ReauthXMPPClient.__init__(self, jid=jid.JID("%s/%s"%(user.jid,conf.XMPP_RESOURCE)), password=user.token, host="talk.google.com", port=5222, logid=user.userid)
        Observer.__init__(self)
        self.user = user
        self.retries = 0
        self.logTraffic = conf.XMPP_LOG_TRAFFIC
        
        #Initialize protocol
        self.handler = GoogleHandler(self)
        protocol = CompleteBotProtocol(self.handler)
        protocol.setHandlerParent(self)
        self.setServiceParent(app)
        
        #Register in XMPP_KEEPALIVE_SERVICE
        KatooApp().getService('XMPP_KEEPALIVE_SUPERVISOR').registerObserver(self)
    
    def notify(self):
        #Check if it is mandatory to do AUTH_RENEWAL
        current_time = Timer().utcnow()
        if (current_time - self.lastTimeAuth).seconds >= self.AUTH_RENEWAL_TIME:
            self.log.info('Launching AUTH_RENEWAL as periodic task')
            self.onAuthenticationRenewal(reason=None)
        
        #Send Keep Alive
        return self.handler.protocol.send(' ')
    
    @property
    def name(self):
        return self.user.userid
    
    @property
    def roster(self):
        return self.handler.roster
    
    @IncrementMetric(name='error_stream', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def _onStreamError(self, reason):
        self.log.err(reason, 'STREAM_EROR_EVENT %s'%(self.user.jid))
    
    @IncrementMetric(name='authentication_renewal', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def onAuthenticationRenewal(self, reason):
        self.log.info('AUTH_RENEWAL_EVENT %s', self.user.jid)
        postdata={'client_id': conf.GOOGLE_CLIENT_ID, 'client_secret': conf.GOOGLE_CLIENT_SECRET, 'refresh_token': self.user.refreshtoken, 'grant_type': 'refresh_token'}
        e = ''
        try:
            #response = yield cyclone.httpclient.fetch(url=conf.GOOGLE_OAUTH2_URL, postdata=postdata)
            response = yield cyclone.httpclient.fetch(conf.GOOGLE_OAUTH2_URL, postdata=urllib.urlencode(postdata))
            if response.code != 200:
                raise ValueError('Wrong response code:%s. Body: %s'%(response.code, response.body))
            data = json.loads(response.body)
            self.log.debug('AUTH_RENEWAL_NEW_DATA %s. New auth data: %s', self.user.jid, data)
            self.user.token = data['access_token']
            #Updating authenticator password with new credentials
            self.factory.authenticator.password = self.user.token
            self._lastTimeAuth = Timer().utcnow()
            yield self.user.save()
        except Exception as ex:
            e = ex
            self.log.err(e, 'AUTH_RENEWAL_ERROR %s'%(self.user.jid))
        finally:
            #Calling to super to perform default behaviour (decrement counter to stop connection in the next retry if not success)
            ReauthXMPPClient.onAuthenticationRenewal(self, e)
    
    @IncrementMetric(name='error_authentication', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onAuthenticationError(self, reason):
        self.log.err(reason, 'AUTH_ERROR_EVENT %s'%(self.user.jid))
        if self.user.pushtoken:
            API(self.user.userid).sendpush(message=translate.TRANSLATORS[self.user.lang]._('authfailed'), token=self.user.pushtoken, badgenumber=self.user.badgenumber, sound='')
        return self.disconnect()
    
    @IncrementMetric(name='error_maxretries', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onMaxRetries(self):
        self.log.error('CONNECTION_MAX_RETRIES %s', self.user.jid)
        if self.user.pushtoken:
            API(self.user.userid).sendpush(message=translate.TRANSLATORS[self.user.lang]._('maxretries'), token=self.user.pushtoken, badgenumber=self.user.badgenumber, sound='')
        return self.disconnect()
    
    @IncrementMetric(name='disconnect', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def disconnect(self, change_state=True):
        self.log.info('DISCONNECTED %s', self.user.jid)
        #Unregister in XMPP_KEEPALIVE_SERVICE
        KatooApp().getService('XMPP_KEEPALIVE_SUPERVISOR').unregisterObserver(self)
        
        deferred_list = [defer.maybeDeferred(self.disownServiceParent)]
        if change_state:
            self.user.away = True
            self.user.connected = False
            deferred_list.append(self.user.save())
            deferred_list.append(GoogleMessage.updateRemoveTime(self.user.userid, self.user.lastTimeConnected))
            deferred_list.append(GoogleRosterItem.remove(self.user.userid))
        return defer.DeferredList(deferred_list, consumeErrors=True)
    
    def __str__(self):
        return '<%s object at %s. name: %s>(user: %s)'%(self.__class__.__name__, hex(id(self)), self.name, vars(self.user))

if __name__ == '__main__':
    import os
    from twisted.internet import reactor
    from katoo.data import GoogleUser
    from wokkel_extensions import XMPPClient
    from katoo.utils.applog import getLogger, getLoggerAdapter
    from katoo.apns.api import KatooAPNSService
    from katoo.supervisor import XMPPKeepAliveSupervisor
    
    my_log = getLoggerAdapter(getLogger(__name__, level="INFO"), id='MYLOG')
    
    app = KatooApp().app
    KatooAPNSService().service.setServiceParent(app)
    KatooApp().start()
    XMPPKeepAliveSupervisor().setServiceParent(app)
    
    import twisted.python.log
    twisted.python.log.startLoggingWithObserver(KatooApp().log.emit)
    xmppclient = XMPPGoogle(GoogleUser("1", _token=os.getenv('TOKEN'), _refreshtoken=os.getenv('REFRESHTOKEN'), _resource="asdfasdf", _pushtoken=os.getenv('PUSHTOKEN', None), _jid=os.getenv('JID'), _pushsound='cell1.aif', _favoritesound='cell7.aif', _away=True), app)
    xmppclient.log.info("Instance XMPPGoogle %s. Instance ReauthXMPP %s Instance XMPPClient %s Instance GoogleUser %s", isinstance(xmppclient, XMPPGoogle), isinstance(xmppclient, ReauthXMPPClient), isinstance(xmppclient, XMPPClient), isinstance(xmppclient, GoogleUser))
    reactor.run()