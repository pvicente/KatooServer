'''
Created on May 13, 2013

@author: pvicente
'''
#===============================================================================
#from twisted.words.xish import domish
#from wokkel.xmppim import AvailablePresence

# class EchoBotProtocol(MessageProtocol):
#     def connectionMade(self):
#         print "Connected!"
# 
#         # send initial presence
#         self.send(AvailablePresence())
# 
#     def connectionLost(self, reason):
#         print "Disconnected!"
# 
#     def onMessage(self, msg):
#         print str(msg)
# 
#         if msg["type"] == 'chat' and hasattr(msg, "body"):
#             reply = domish.Element((None, "message"))
#             reply["to"] = msg["from"]
#             reply["from"] = msg["to"]
#             reply["type"] = 'chat'
#             reply.addElement("body", content="echo: " + str(msg.body))
# 
#             self.send(reply)
#===============================================================================
from wokkel.xmppim import MessageProtocol, PresenceClientProtocol, \
    RosterClientProtocol

class CompleteBotProtocol(MessageProtocol, RosterClientProtocol, PresenceClientProtocol):
    
    def __init__(self, xmpphandler):
        MessageProtocol.__init__(self)
        self._xmpphandler = xmpphandler
        self._xmpphandler.setProtocol(self)
    
    def connectionInitialized(self):
        MessageProtocol.connectionInitialized(self)
        RosterClientProtocol.connectionInitialized(self)
        PresenceClientProtocol.connectionInitialized(self)
        
        #Send Available and getting roster
        self.available()
        d = self.getRoster()
        d.addCallback(self.onRosterReceived)
        
        #Call to handler
        self._xmpphandler.onAuthenticated()
    
    def connectionMade(self):
        self._xmpphandler.onConnectionEstablished()
    
    def connectionLost(self, reason):
        self._xmpphandler.onConnectionLost(reason)
    
    def availableReceived(self, entity, show=None, statuses=None, priority=0):
        """
        Available presence was received.

        @param entity: entity from which the presence was received.
        @type entity: {JID}
        @param show: detailed presence information. One of C{'away'}, C{'xa'},
                     C{'chat'}, C{'dnd'} or C{None}.
        @type show: C{str} or C{NoneType}
        @param statuses: dictionary of natural language descriptions of the
                         availability status, keyed by the language
                         descriptor. A status without a language
                         specified, is keyed with C{None}.
        @type statuses: C{dict}
        @param priority: priority level of the resource.
        @type priority: C{int}
        """
        self._xmpphandler.onAvailableReceived(entity)
   
    def unavailableReceived(self, entity, statuses=None):
        """
        Unavailable presence was received.

        @param entity: entity from which the presence was received.
        @type entity: {JID}
        @param statuses: dictionary of natural language descriptions of the
                         availability status, keyed by the language
                         descriptor. A status without a language
                         specified, is keyed with C{None}.
        @type statuses: C{dict}
        """
        self._xmpphandler.onUnavailableReceived(entity)
    
    def onRosterSet(self, item):
        self._xmpphandler.onRosterSet(item)
    
    def onRosterRemove(self, item):
        self._xmpphandler.onRosterRemove(item)
    
    def onRosterReceived(self, roster):
        self._xmpphandler.onRosterReceived(roster)
    
    def onMessage(self, msg):
        self._xmpphandler.onMessageReceived(msg)
    
