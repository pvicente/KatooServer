'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import conf
from twisted.python import log
from twisted.words.protocols.jabber import jid
from wokkel_extensions import ReauthXMPPClient
from xmppprotocol import CompleteBotProtocol

class XMPPGoogleClient(ReauthXMPPClient):
    def __init__(self, user, app):
        self.user = user
        ReauthXMPPClient.__init__(self, jid=jid.internJID("user@gmail.com"), password=user.token, host="talk.google.com", port=5222)
        self.logTraffic = conf.XMPP_LOG_TRAFFIC
        protocol = CompleteBotProtocol()
        protocol.setHandlerParent(self)
        self.setServiceParent(app)
    
    @property
    def name(self):
        return self.user.userid
    
    def onAuthenticationRenewal(self, reason):
        #TODO: implement oauth2 new challenge. Not call to parent method
        ReauthXMPPClient.onAuthenticationRenewal(self, reason)
    
    def __str__(self):
        return '<%s object at %s. name: %s>(user: %s)'%(self.__class__.__name__, hex(id(self)), self.name, vars(self.user))


if __name__ == '__main__':
    import sys, os
    from twisted.internet import reactor
    from katoo.data import XMPPGoogleUser
    from katoo import KatooApp

    log.startLogging(sys.stdout)
    app = KatooApp().app
    XMPPGoogleClient(XMPPGoogleUser("1", token=os.getenv('TOKEN'), refreshtoken='kk', resource="asdfasdf"), app)
    KatooApp().start()
    reactor.run()