'''
Created on May 25, 2013

@author: pvicente
'''
import os
from twisted.application import service
from twisted.words.protocols.jabber import jid
from katoo.xmpp.wokkel_extensions import ReauthXMPPClient
from katoo.xmpp.xmppprotocol import CompleteBotProtocol, GenericXMPPHandler

application = service.Application("facebookbot")
appid = os.getenv("APPID", '')
token = os.getenv('TOKEN', '')

xmppclient = ReauthXMPPClient(jid=jid.internJID("%s@chat.facebook.com/test"%(appid)), password=token, host="chat.facebook.com")
xmppclient.logTraffic = True
handler = GenericXMPPHandler(xmppclient)
bot = CompleteBotProtocol(handler)
bot.setHandlerParent(xmppclient)
xmppclient.setServiceParent(application)