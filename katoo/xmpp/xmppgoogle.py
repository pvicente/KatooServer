'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import conf
from katoo.apns.api import sendchatmessage, sendcustom
from katoo.data import GoogleMessage
from twisted.internet import defer
from twisted.python import log
from twisted.words.protocols.jabber import jid
from wokkel_extensions import ReauthXMPPClient
from xmppprotocol import CompleteBotProtocol, GenericXMPPHandler
import cyclone.httpclient
import json
import time
import urllib

class GoogleHandler(GenericXMPPHandler):
    ROSTER_IN_MEMORY=conf.XMPP_ROSTER_IN_MEMORY
    def __init__(self, client):
        GenericXMPPHandler.__init__(self, client)
        self.user = client.user
        self.roster = {}
        self.connectionTime = None
    
    def getName(self, jid):
        try:
            name = self.roster[jid].name
            return (name,jid.userhost()) if name else (jid.user, jid.userhost())
        except KeyError:
            return (jid.user, jid.userhost())
    
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
        log.msg('XMPP_GO_ONLINE %s:%s -> %s@%s/%s'%(self.user.userid, self.user.jid, jid.user, jid.host, jid.resource))
    
    def onUnavailableReceived(self, jid):
        if self.isOwnBareJid(jid) and jid.resource == self.user.resource:
            log.msg('APP_GO_AWAY %s:%s'%(self.user.userid, self.user.jid))
            self.user.away = True
            return self.user.save()
        log.msg('XMPP_GO_OFFLINE %s:%s -> %s@%s/%s'%(self.user.userid, self.user.jid, jid.user, jid.host, jid.resource))
    
    def onRosterReceived(self, roster):
        if self.ROSTER_IN_MEMORY:
            self.roster = roster
    
    def onRosterSet(self, item):
        pass
    
    def onRosterRemove(self, item):
        pass
    
    def onMessageReceived(self, fromjid, msgid, body):
        log.msg("MESSAGE_RECEIVED %s:%s. msgid(%s) from(%s): %r"%(self.user.userid, self.user.jid, msgid, fromjid, body))
        fromname, barejid = self.getName(fromjid)
        message = GoogleMessage(userid=self.user.userid, fromid=barejid, msgid=msgid, data=body)
        d = message.save()
        if self.user.pushtoken and self.user.away:
            log.msg('SENDING_PUSH %s:%s. User data: %s'%(self.user.userid, self.user.jid, self.user))
            d.addCallback(lambda x: sendchatmessage(msg=body, token=self.user.pushtoken, sound=self.user.pushsound, badgenumber=self.user.badgenumber, jid=barejid, fullname=fromname))
            self.user.badgenumber += 1
            d.addCallback(lambda x: self.user.save())
        return d
    
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
            self.user.connected = False
            d.addCallback(lambda x: self.user.save())
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
    XMPPGoogle(GoogleUser("1", _token=os.getenv('TOKEN'), _refreshtoken=os.getenv('REFRESHTOKEN'), _resource="asdfasdf", _pushtoken=os.getenv('PUSHTOKEN', None), _jid=os.getenv('JID')), app)
    KatooApp().start()
    reactor.run()