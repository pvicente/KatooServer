'''
Created on May 25, 2013

@author: pvicente
'''
import os
from twisted.application import service
from twisted.words.protocols.jabber import jid
from katoo.wokkel_extensions import ExtendedXMPPClient
from katoo.xmppbot import CompleteBotProtocol

application = service.Application("gtalkbot")
username = os.getenv("USERNAME", 'pedro.vicente.fernandez@gmail.com/Messaging')
token = os.getenv('TOKEN', '')

xmppclient = ExtendedXMPPClient(jid=jid.internJID(username), password=token, host="talk.google.com")
xmppclient.logTraffic = True
bot = CompleteBotProtocol()
bot.setHandlerParent(xmppclient)
xmppclient.setServiceParent(application)