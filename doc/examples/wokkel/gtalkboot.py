'''
Created on May 25, 2013

@author: pvicente
'''
import os
from twisted.application import service
from twisted.words.protocols.jabber import jid
from katoo.xmpp.wokkel_extensions import ExtendedXMPPClient
from katoo.xmpp.xmppbot import CompleteBotProtocol

application = service.Application("gtalkbot")
username = os.getenv("USERNAME", 'user@gmail.com')
token = os.getenv('TOKEN', '')

xmppclient = ExtendedXMPPClient(jid=jid.internJID(username), password=token, host="talk.google.com")
xmppclient.logTraffic = True
bot = CompleteBotProtocol()
bot.setHandlerParent(xmppclient)
xmppclient.setServiceParent(application)