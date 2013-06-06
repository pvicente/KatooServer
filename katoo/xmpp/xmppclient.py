'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import conf
from twisted.words.protocols.jabber import jid
from wokkel_extensions import ExtendedXMPPClient
from xmppbot import CompleteBotProtocol

class XMPPGoogleClient(ExtendedXMPPClient):
    def __init__(self, user, app):
        self.user = user
        ExtendedXMPPClient.__init__(self, jid=jid.internJID("user@gmail.com"), password=user.token, host="talk.google.com", port=5222)
        self.logTraffic = conf.XMPP_LOG_TRAFFIC
        protocol = CompleteBotProtocol()
        protocol.setHandlerParent(self)
        self.setServiceParent(app)
    
    @property
    def name(self):
        return self.user.userid
    
    def __str__(self):
        return '<%s object at %s. name: %s>(user: %s)'%(self.__class__.__name__, hex(id(self)), self.name, vars(self.user))