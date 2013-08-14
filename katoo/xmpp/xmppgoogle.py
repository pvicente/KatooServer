'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import conf
from katoo.apns.api import API
from katoo.data import GoogleMessage, GoogleRosterItem
from twisted.internet import defer
from twisted.words.protocols.jabber import jid
from wokkel_extensions import ReauthXMPPClient
from xmppprotocol import CompleteBotProtocol, GenericXMPPHandler
import cyclone.httpclient
import json
import time
import urllib
from katoo.metrics import IncrementMetric

METRIC_SOURCE='XMPPGOOGLE'
METRIC_UNIT='events'

class RosterManager(object):
    ROSTER_IN_MEMORY=conf.XMPP_ROSTER_IN_MEMORY
    def __init__(self, userid, log):
        self._userid = userid
        self._roster = {}
        self.log = log
    
    @defer.inlineCallbacks
    def processRoster(self, roster):
        for k,v in roster.iteritems():
            defaultName = k.user if isinstance(k, jid.JID) else k
            name = getattr(v, 'name', '')
            name = name if name else defaultName
            yield self.set(k,name=name)
    
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
    def __init__(self, client):
        GenericXMPPHandler.__init__(self, client)
        self.user = client.user
        self.roster = RosterManager(self.user.userid, self.log)
        self.connectionTime = None
    
    def isOwnBareJid(self, jid):
        return self.client.jid.user == jid.user and self.client.jid.host == jid.host
    
    @IncrementMetric(name='xmppgoogle_connection_established', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onConnectionEstablished(self):
        self.connectionTime = None
        self.log.info('CONNECTION_ESTABLISHED %s', self.user.jid)
    
    @IncrementMetric(name='xmppgoogle_connection_lost', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onConnectionLost(self, reason):
        connectedTime = 0 if self.connectionTime is None else time.time() - self.connectionTime
        isAuthenticating = self.client.isAuthenticating()
        self.log.info('CONNECTION_LOST %s. Connected Time: %s. Authenticating: %s. Reason %s', self.user.jid, connectedTime, isAuthenticating, str(reason))
        if not isAuthenticating:
            if connectedTime < conf.XMPP_MIN_CONNECTED_TIME:
                self.client.retries += 1
                if self.client.retries >= conf.XMPP_MAX_RETRIES:
                    self.client.onMaxRetries()
                    return
            else:
                self.client.retries = 0
    
    @IncrementMetric(name='xmppgoogle_connection_authenticated', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onAuthenticated(self):
        self.connectionTime = time.time()
        self.log.info('CONNECTION_AUTHENTICATED %s', self.user.jid)
        
        #Set away state to be restored with right value when presences will be received
        self.user.away = True
        self.user.save()
        
        #Send Available and getting roster
        self.protocol.available(show=conf.XMPP_STATE, priority=conf.XMPP_PRIORITY, statuses={'en-US': conf.XMPP_MOOD})
        d = self.protocol.getRoster()
        d.addCallback(self.protocol.onRosterReceived)
        
    
    @IncrementMetric(name='xmppgoogle_presence_available', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onAvailableReceived(self, jid):
        if self.isOwnBareJid(jid) and jid.resource == self.user.resource:
            self.log.info('APP_GO_ONLINE %s',self.user.jid)
            self.user.away = False
            return self.user.save()
        self.log.debug('XMPP_GO_ONLINE %s <- %s@%s/%r', self.user.jid, jid.user, jid.host, jid.resource)
    
    @IncrementMetric(name='xmppgoogle_presence_unavailable', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onUnavailableReceived(self, jid):
        if self.isOwnBareJid(jid) and jid.resource == self.user.resource:
            self.log.info('APP_GO_AWAY %s', self.user.jid)
            self.user.away = True
            return self.user.save()
        self.log.debug('XMPP_GO_OFFLINE %s <- %s@%s/%r', self.user.jid, jid.user, jid.host, jid.resource)
    
    @IncrementMetric(name='xmppgoogle_roster_received', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onRosterReceived(self, roster):
        self.roster.processRoster(roster)
    
    @IncrementMetric(name='xmppgoogle_roster_set', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onRosterSet(self, item):
        pass
    
    @IncrementMetric(name='xmppgoogle_roster_remove', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onRosterRemove(self, item):
        pass
    
    @IncrementMetric(name='xmppgoogle_message_received', unit=METRIC_UNIT, source=METRIC_SOURCE)
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
                self.user.badgenumber += 1
                self.log.debug('SENDING_PUSH %s. RosterItem: %s, User data: %s', self.user.jid, roster_item, self.user)
                yield API(self.user.userid).sendchatmessage(msg=body, token=self.user.pushtoken, badgenumber=self.user.badgenumber, jid=roster_item.jid, fullname=roster_item.contactName, 
                                                            sound=self.user.favoritesound if roster_item.favorite else self.user.pushsound, emoji= u'\ue32f' if roster_item.favorite else '')
                self.log.debug('PUSH SENT %s', self.user.jid)
                yield self.user.save()
        except Exception as e:
            self.log.err(e, 'ON_MESSAGE_RECEIVED_EXCEPTION')
    
class XMPPGoogle(ReauthXMPPClient):
    def __init__(self, user, app):
        ReauthXMPPClient.__init__(self, jid=jid.JID("%s/%s"%(user.jid,conf.XMPP_RESOURCE)), password=user.token, host="talk.google.com", port=5222, logid=user.userid)
        self.user = user
        self.retries = 0
        self.logTraffic = conf.XMPP_LOG_TRAFFIC
        
        #Initialize protocol
        self.handler = GoogleHandler(self)
        protocol = CompleteBotProtocol(self.handler)
        protocol.setHandlerParent(self)
        self.setServiceParent(app)
        
    
    @property
    def name(self):
        return self.user.userid
    
    @property
    def roster(self):
        return self.handler.roster
    
    @IncrementMetric(name='xmppgoogle_error_stream', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def _onStreamError(self, reason):
        self.log.err(reason, 'STREAM_EROR_EVENT %s'%(self.user.jid))
    
    @IncrementMetric(name='xmppgoogle_authentication_renewal', unit=METRIC_UNIT, source=METRIC_SOURCE)
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
            yield self.user.save()
        except Exception as ex:
            e = ex
            self.log.err(e, 'AUTH_RENEWAL_ERROR %s'%(self.user.jid))
        finally:
            #Calling to super to perform default behaviour (decrement counter to stop connection in the next retry if not success)
            ReauthXMPPClient.onAuthenticationRenewal(self, e)
    
    @IncrementMetric(name='xmppgoogle_error_authentication', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onAuthenticationError(self, reason):
        self.log.err(reason, 'AUTH_ERROR_EVENT %s'%(self.user.jid))
        if self.user.pushtoken:
            API(self.user.userid).sendcustom(lang=self.user.lang, token=self.user.pushtoken, badgenumber=self.user.badgenumber, type_msg='authfailed', sound='')
        return self.disconnect()
    
    @IncrementMetric(name='xmppgoogle_error_maxretries', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def onMaxRetries(self):
        self.log.error('CONNECTION_MAX_RETRIES %s', self.user.jid)
        if self.user.pushtoken:
            API(self.user.userid).sendcustom(lang=self.user.lang, token=self.user.pushtoken, badgenumber=self.user.badgenumber, type_msg='maxretries', sound='')
        return self.disconnect()
    
    @IncrementMetric(name='xmppgoogle_disconnect', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def disconnect(self, change_state=True):
        self.log.info('DISCONNECTED %s', self.user.jid)
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
    from katoo import KatooApp
    from wokkel_extensions import XMPPClient
    from twisted.internet.task import LoopingCall
    from katoo.utils.applog import getLogger, getLoggerAdapter
    from katoo.apns.api import KatooAPNSService
    
    my_log = getLoggerAdapter(getLogger(__name__, level="INFO"), id='MYLOG')
    
    @defer.inlineCallbacks
    def keep_alive(client):
        handler = getattr(client, 'handler', None)
        protocol = None if handler is None else getattr(handler, 'protocol', None)
        my_log.info('Handler %s Protocol %s', handler, protocol)
        if protocol:
            
            yield protocol.send(' ')
    
    app = KatooApp().app
    KatooAPNSService().service.setServiceParent(app)
    KatooApp().start()
    import twisted.python.log
    twisted.python.log.startLoggingWithObserver(KatooApp().log.emit)
    xmppclient = XMPPGoogle(GoogleUser("1", _token=os.getenv('TOKEN'), _refreshtoken=os.getenv('REFRESHTOKEN'), _resource="asdfasdf", _pushtoken=os.getenv('PUSHTOKEN', None), _jid=os.getenv('JID'), _pushsound='cell1.aif', _favoritesound='cell7.aif', _away=True), app)
    xmppclient.log.info("Instance XMPPGoogle %s. Instance ReauthXMPP %s Instance XMPPClient %s Instance GoogleUser %s", isinstance(xmppclient, XMPPGoogle), isinstance(xmppclient, ReauthXMPPClient), isinstance(xmppclient, XMPPClient), isinstance(xmppclient, GoogleUser))
    t = LoopingCall(keep_alive, xmppclient)
    t.start(1, now=False)
    reactor.run()