'''
Created on May 25, 2013

@author: pvicente
'''
import os
from twisted.application import service
from twisted.words.protocols.jabber import jid
from katoo.xmpp.wokkel_extensions import ReauthXMPPClient
from katoo.xmpp.xmppprotocol import CompleteBotProtocol, GenericXMPPHandler

application = service.Application("gtalkbot")
username = os.getenv("USERNAME", 'user@gmail.com')
token = os.getenv('TOKEN', '')

xmppclient = ReauthXMPPClient(jid=jid.internJID(username), password=token, host="talk.google.com")
xmppclient.logTraffic = True
handler = GenericXMPPHandler(xmppclient)
bot = CompleteBotProtocol(handler)
bot.setHandlerParent(xmppclient)
xmppclient.setServiceParent(application)