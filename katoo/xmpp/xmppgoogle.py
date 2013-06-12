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
import urllib

class GoogleHandler(GenericXMPPHandler):
    ROSTER_IN_MEMORY=conf.XMPP_ROSTER_IN_MEMORY
    def __init__(self, client):
        GenericXMPPHandler.__init__(self, client)
        self.user = client.user
        self.roster = {}
    
    def getName(self, jid):
        try:
            name = self.roster[jid].name
            return (name,jid.userhost()) if name else (jid.user, jid.userhost())
        except KeyError:
            return (jid.user, jid.userhost())
    
    def isOwnBareJid(self, jid):
        return self.client.jid.user == jid.user and self.client.jid.host == jid.host
    
    def onConnectionEstablished(self):
        pass
    
    def onConnectionLost(self, reason):
        pass
    
    def onAuthenticated(self):
        pass
    
    def onAvailableReceived(self, jid):
        if self.isOwnBareJid(jid) and jid.resource == self.user.resource:
            self.user.away = False
            return self.user.save()
    
    def onUnavailableReceived(self, jid):
        if self.isOwnBareJid(jid) and jid.resource == self.user.resource:
            self.user.away = True
            return self.user.save()
    
    def onRosterReceived(self, roster):
        if self.ROSTER_IN_MEMORY:
            self.roster = roster
    
    def onRosterSet(self, item):
        pass
    
    def onRosterRemove(self, item):
        pass
    
    def onMessageReceived(self, fromjid, msgid, body):
        log.msg("received msgid(%s) from(%s): %r"%(msgid, fromjid, body))
        fromname, barejid = self.getName(fromjid)
        message = GoogleMessage(userid=self.user.userid, fromid=barejid, msgid=msgid, data=body)
        d = message.save()
        if self.user.pushtoken and self.user.away:
            log.msg('sending push to user %s'%(self.user))
            d.addCallback(lambda x: sendchatmessage(msg=body, token=self.user.pushtoken, sound=self.user.pushsound, badgenumber=self.user.badgenumber, jid=barejid, fullname=fromname))
            self.user.badgenumber += 1
            d.addCallback(lambda x: self.user.save())
        return d
    
class XMPPGoogle(ReauthXMPPClient):
    def __init__(self, user, app):
        ReauthXMPPClient.__init__(self, jid=jid.internJID("user@gmail.com"), password=user.token, host="talk.google.com", port=5222)
        self.user = user
        self.logTraffic = conf.XMPP_LOG_TRAFFIC
        
        #Initialize protocol
        handler = GoogleHandler(self)
        protocol = CompleteBotProtocol(handler)
        protocol.setHandlerParent(self)
        self.setServiceParent(app)
    
    @property
    def name(self):
        return self.user.userid
    
    @defer.inlineCallbacks
    def onAuthenticationRenewal(self, reason):
        log.msg('Authentication error: requesting new access token for user %s with refresh_token %s'%(self.user.userid, self.user.refreshtoken))
        postdata={'client_id': conf.GOOGLE_CLIENT_ID, 'client_secret': conf.GOOGLE_CLIENT_SECRET, 'refresh_token': self.user.refreshtoken, 'grant_type': 'refresh_token'}
        e = ''
        try:
            #response = yield cyclone.httpclient.fetch(url=conf.GOOGLE_OAUTH2_URL, postdata=postdata)
            response = yield cyclone.httpclient.fetch(conf.GOOGLE_OAUTH2_URL, postdata=urllib.urlencode(postdata))
            if response.code != 200:
                raise ValueError('Wrong response code:%s. Body: %s'%(response.code, response.body))
            data = json.loads(response.body)
            log.msg('Authentication renewal user %s, jid %s. New auth data: %s'%(self.user.userid, self.user.jid, data))
            self.user.token = data['access_token']
            #Updating authenticator password with new credentials
            self.factory.authenticator.password = self.user.token
            yield self.user.save()
        except Exception as ex:
            e = ex
            log.err(e)
        finally:
            #Calling to super to perform default behaviour (decrement counter to stop connection in the next retry if not success)
            ReauthXMPPClient.onAuthenticationRenewal(self, e)
    
    def onAuthenticationError(self, reason):
        log.err(reason)
        if self.user.pushtoken:
            sendcustom(lang=self.user.lang, token=self.user.pushtoken, badgenumber=self.user.badgenumber, type_msg='auth_failed', sound='')
        return self.disconnect()
    
    def disconnect(self, change_state=True):
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
    XMPPGoogle(GoogleUser("1", _token=os.getenv('TOKEN'), _refreshtoken=os.getenv('REFRESHTOKEN'), _resource="asdfasdf", _pushtoken=os.getenv('PUSHTOKEN', None), _jid="kk@gmail.com" ), app)
    KatooApp().start()
    reactor.run()