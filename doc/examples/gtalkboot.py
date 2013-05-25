'''
Created on May 25, 2013

@author: pvicente
'''
import os
from twisted.application import service
from twisted.words.protocols.jabber import jid
from wokkel.client import XMPPClient
from katoo.xmppbot import CompleteBotProtocol

application = service.Application("gtalkbot")
username = os.getenv("USERNAME", 'user@gmail.com')
token = os.getenv('TOKEN', '')

xmppclient = XMPPClient(jid=jid.internJID(username), password=token, host="talk.google.com")
xmppclient.logTraffic = True
bot = CompleteBotProtocol()
bot.setHandlerParent(xmppclient)
xmppclient.setServiceParent(application)