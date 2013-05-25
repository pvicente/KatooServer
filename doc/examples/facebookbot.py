'''
Created on May 25, 2013

@author: pvicente
'''
import os
from twisted.application import service
from twisted.words.protocols.jabber import jid
from wokkel.client import XMPPClient
from katoo.xmppbot import CompleteBotProtocol

application = service.Application("facebookbot")
appid = os.getenv("APPID", '')
token = os.getenv('TOKEN', '')

xmppclient = XMPPClient(jid=jid.internJID("%s@chat.facebook.com"%(appid)), password=token, host="chat.facebook.com")
xmppclient.logTraffic = True
bot = CompleteBotProtocol()
bot.setHandlerParent(xmppclient)
xmppclient.setServiceParent(application)