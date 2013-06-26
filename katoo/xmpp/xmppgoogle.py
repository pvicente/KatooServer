'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import conf
from katoo.apns.api import sendchatmessage, sendcustom
from katoo.data import GoogleMessage, GoogleContact, GoogleRosterItem
from twisted.internet import defer
from twisted.python import log
from twisted.words.protocols.jabber import jid
from wokkel_extensions import ReauthXMPPClient
from xmppprotocol import CompleteBotProtocol, GenericXMPPHandler
import cyclone.httpclient
import json
import time
import urllib

class RosterManager(object):
    ROSTER_IN_MEMORY=conf.XMPP_ROSTER_IN_MEMORY
    def __init__(self, userid):
        self._userid = userid
        self._roster = {}
    
    @defer.inlineCallbacks
    def processRoster(self, roster):
        for k,v in roster.iteritems():
            yield self.set(k,v)
    
    def _getBareJid(self, key):
        if isinstance(key, jid.JID):
            return key.userhost()
        else:
            return key
    
    @defer.inlineCallbacks
    def get(self, key, default=None):
        if self.ROSTER_IN_MEMORY:
            defer.returnValue(self._roster.get(key, default))
        
        barejid = self._getBareJid(key)
        ret = yield GoogleRosterItem.load(self._userid, barejid)
        defer.returnValue(default if ret is None else ret)
    
    @defer.inlineCallbacks
    def set(self, key, value):
        defaultName = key.user if isinstance(key, jid.JID) else key
        barejid = self._getBareJid(key)
        name = getattr(value, 'name', None)
        item = GoogleRosterItem(_userid=self._userid, _jid=barejid, _name=name if name else defaultName)
        if self.ROSTER_IN_MEMORY:
            self._roster[barejid] = item
        else:
            yield item.save()
        defer.returnValue(None)
    
class ContactInformation(object):
    @classmethod
    def _load_callback(cls, user, roster_item, contact):
        return cls(user, roster_item, contact)
    
    @classmethod
    def load(cls, user, roster_item):
        d = GoogleContact.load(user.userid, roster_item.jid)
        d.addCallback(lambda x: cls._load_callback(user, roster_item, x))
        d.addErrback(log.err)
        return d
    
    def __init__(self, user, roster_item, contact):
        self.name = roster_item.name
        self.barejid = roster_item.jid
        self.favorite = False
        self.emoji = ''
        self.sound = user.pushsound
        if not contact is None:
            self.name = contact.name if contact.name else self.name
            if contact.favorite:
                self.favorite=True
                self.emoji = u'\ue335'
                if self.sound:
                    self.sound = user.favoritesound
    
    def __str__(self):
        return '<%s object at %s>(%s)'%(self.__class__.__name__, hex(id(self)), vars(self))
    
class GoogleHandler(GenericXMPPHandler):
    def __init__(self, client):
        GenericXMPPHandler.__init__(self, client)
        self.user = client.user
        self.roster = RosterManager(self.user.userid)
        self.connectionTime = None
    
    def isOwnBareJid(self, jid):
        return self.client.jid.user == jid.user and self.client.jid.host == jid.host
    
    def onConnectionEstablished(self):
        self.connectionTime = None
        log.msg('CONNECTION_ESTABLISHED %s:%s'%(self.user.userid, self.user.jid))
    
    def onConnectionLost(self, reason):
        connectedTime = 0 if self.connectionTime is None else time.time() - self.connectionTime
        isAuthenticating = self.client.isAuthenticating()
        log.msg('CONNECTION_LOST %s:%s. Connected Time: %s. Authenticating: %s. Reason %s'%(self.user.userid, self.user.jid, connectedTime, isAuthenticating, str(reason)))
        if not isAuthenticating:
            if connectedTime < conf.XMPP_MIN_CONNECTED_TIME:
                self.client.retries += 1
                if self.client.retries >= conf.XMPP_MAX_RETRIES:
                    self.client.onMaxRetries()
                    return
            else:
                self.client.retries = 0
    
    def onAuthenticated(self):
        self.connectionTime = time.time()
        log.msg('CONNECTION_AUTHENTICATED %s:%s'%(self.user.userid, self.user.jid))
    
    def onAvailableReceived(self, jid):
        if self.isOwnBareJid(jid) and jid.resource == self.user.resource:
            log.msg('APP_GO_ONLINE %s:%s'%(self.user.userid, self.user.jid))
            self.user.away = False
            return self.user.save()
        log.msg('XMPP_GO_ONLINE %s:%s -> %s@%s/%r'%(self.user.userid, self.user.jid, jid.user, jid.host, jid.resource))
    
    def onUnavailableReceived(self, jid):
        if self.isOwnBareJid(jid) and jid.resource == self.user.resource:
            log.msg('APP_GO_AWAY %s:%s'%(self.user.userid, self.user.jid))
            self.user.away = True
            return self.user.save()
        log.msg('XMPP_GO_OFFLINE %s:%s -> %s@%s/%r'%(self.user.userid, self.user.jid, jid.user, jid.host, jid.resource))
    
    def onRosterReceived(self, roster):
        self.roster.processRoster(roster)
    
    def onRosterSet(self, item):
        pass
    
    def onRosterRemove(self, item):
        pass
    
    @defer.inlineCallbacks
    def onMessageReceived(self, fromjid, msgid, body):
        log.msg("MESSAGE_RECEIVED %s:%s. msgid(%s) from(%s): %r"%(self.user.userid, self.user.jid, msgid, fromjid, body))
        barefromjid=fromjid.userhost()
        message = GoogleMessage(userid=self.user.userid, fromid=barefromjid, msgid=msgid, data=body)
        yield message.save()
        if self.user.pushtoken and self.user.away:
            roster_item = yield self.roster.get(barefromjid)
            if roster_item is None:
                roster_item = GoogleRosterItem(_userid=self.user.userid, _jid=barefromjid, _name=fromjid.user)
            contact_info = yield ContactInformation.load(self.user, roster_item)
            log.msg('SENDING_PUSH %s:%s. RosterItem: %s Contact Info: %s, User data: %s'%(self.user.userid, self.user.jid, roster_item, contact_info, self.user))
            self.user.badgenumber += 1
            yield sendchatmessage(msg=body, token=self.user.pushtoken, badgenumber=self.user.badgenumber, jid=contact_info.barejid, fullname=contact_info.name, sound=contact_info.sound, emoji=contact_info.emoji)
            yield self.user.save()
    
class XMPPGoogle(ReauthXMPPClient):
    def __init__(self, user, app):
        ReauthXMPPClient.__init__(self, jid=jid.JID("%s/%s"%(user.jid,conf.XMPP_RESOURCE)), password=user.token, host="talk.google.com", port=5222)
        self.user = user
        self.retries = 0
        self.logTraffic = conf.XMPP_LOG_TRAFFIC
        
        #Initialize protocol
        handler = GoogleHandler(self)
        protocol = CompleteBotProtocol(handler)
        protocol.setHandlerParent(self)
        self.setServiceParent(app)
        
    
    @property
    def name(self):
        return self.user.userid
    
    def _onStreamError(self, reason):
        log.err(reason, 'STREAM_EROR_EVENT %s:%s'%(self.user.userid, self.user.jid))
    
    @defer.inlineCallbacks
    def onAuthenticationRenewal(self, reason):
        log.msg('AUTH_RENEWAL_EVENT %s:%s. with refresh_token %s'%(self.user.userid, self.user.jid, self.user.refreshtoken))
        postdata={'client_id': conf.GOOGLE_CLIENT_ID, 'client_secret': conf.GOOGLE_CLIENT_SECRET, 'refresh_token': self.user.refreshtoken, 'grant_type': 'refresh_token'}
        e = ''
        try:
            #response = yield cyclone.httpclient.fetch(url=conf.GOOGLE_OAUTH2_URL, postdata=postdata)
            response = yield cyclone.httpclient.fetch(conf.GOOGLE_OAUTH2_URL, postdata=urllib.urlencode(postdata))
            if response.code != 200:
                raise ValueError('Wrong response code:%s. Body: %s'%(response.code, response.body))
            data = json.loads(response.body)
            log.msg('AUTH_RENEWAL_NEW_DATA %s:%s. New auth data: %s'%(self.user.userid, self.user.jid, data))
            self.user.token = data['access_token']
            #Updating authenticator password with new credentials
            self.factory.authenticator.password = self.user.token
            yield self.user.save()
        except Exception as ex:
            e = ex
            log.err(e, 'AUTH_RENEWAL_ERROR %s:%s'%(self.user.userid, self.user.jid))
        finally:
            #Calling to super to perform default behaviour (decrement counter to stop connection in the next retry if not success)
            ReauthXMPPClient.onAuthenticationRenewal(self, e)
    
    def onAuthenticationError(self, reason):
        log.err(reason, 'AUTH_ERROR_EVENT %s:%s'%(self.user.userid, self.user.jid))
        if self.user.pushtoken:
            sendcustom(lang=self.user.lang, token=self.user.pushtoken, badgenumber=self.user.badgenumber, type_msg='authfailed', sound='')
        return self.disconnect()
    
    def onMaxRetries(self):
        log.err('CONNECTION_MAX_RETRIES %s:%s'%(self.user.userid, self.user.jid))
        if self.user.pushtoken:
            sendcustom(lang=self.user.lang, token=self.user.pushtoken, badgenumber=self.user.badgenumber, type_msg='maxretries', sound='')
        return self.disconnect()
    
    def disconnect(self, change_state=True):
        log.msg('DISCONNECTED %s:%s'%(self.user.userid, self.user.jid))
        d = defer.maybeDeferred(self.disownServiceParent)
        if change_state:
            self.user.away = True
            self.user.connected = False
            d.addCallback(lambda x: self.user.save())
            d.addCallback(lambda x: GoogleMessage.updateRemoveTime(self.user.userid, self.user.lastTimeConnected))
            d.addCallback(lambda x: GoogleContact.remove(self.user.userid))
            d.addCallback(lambda x: GoogleRosterItem.remove(self.user.userid))
        return d
    
    def __str__(self):
        return '<%s object at %s. name: %s>(user: %s)'%(self.__class__.__name__, hex(id(self)), self.name, vars(self.user))

if __name__ == '__main__':
    import sys, os
    from twisted.internet import reactor
    from katoo.data import GoogleUser
    from katoo import KatooApp
    from katoo.apns import delivery
    from katoo.txapns.txapns.apns import APNSService

    delivery.ApnService = apns = APNSService(cert_path=conf.APNS_CERT, environment=conf.APNS_SANDBOX, timeout=5)
    apns.setName(conf.APNSERVICE_NAME)

    log.startLogging(sys.stdout)
    app = KatooApp().app
    XMPPGoogle(GoogleUser("1", _token=os.getenv('TOKEN'), _refreshtoken=os.getenv('REFRESHTOKEN'), _resource="asdfasdf", _pushtoken=os.getenv('PUSHTOKEN', None), _jid=os.getenv('JID'), _pushsound='cell1.aif', _favoritesound='cell7.aif', _away=True), app)
    KatooApp().start()
    reactor.run()