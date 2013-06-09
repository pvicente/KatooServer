'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import conf
from twisted.internet import defer
from twisted.python import log
from twisted.words.protocols.jabber import jid
from wokkel_extensions import ReauthXMPPClient
from xmppprotocol import CompleteBotProtocol, GenericXMPPHandler

class GoogleHandler(GenericXMPPHandler):
    ROSTER_IN_MEMORY=conf.XMPP_ROSTER_IN_MEMORY
    def __init__(self, client):
        GenericXMPPHandler.__init__(self, client)
        self.user = client.user
        self.roster = None
    
    def onConnectionEstablished(self):
        pass
    
    def onConnectionLost(self, reason):
        pass
    
    def onAuthenticated(self):
        pass
    
    def onAvailableReceived(self, jid):
        pass
    
    def onUnavailableReceived(self, jid):
        pass
    
    def onRosterReceived(self, roster):
        if self.ROSTER_IN_MEMORY:
            self.roster = roster
    
    def onRosterSet(self, item):
        pass
    
    def onRosterRemove(self, item):
        pass
    
    def onMessageReceived(self, msg):
        pass
    
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
    
    def onAuthenticationRenewal(self, reason):
        #TODO: implement oauth2 new challenge. Not call to parent method
        ReauthXMPPClient.onAuthenticationRenewal(self, reason)
    
    def onAuthenticationError(self, reason):
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

    log.startLogging(sys.stdout)
    app = KatooApp().app
    XMPPGoogle(GoogleUser("1", token=os.getenv('TOKEN'), refreshtoken='kk', resource="asdfasdf"), app)
    KatooApp().start()
    reactor.run()