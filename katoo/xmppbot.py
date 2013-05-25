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
import wokkel_extensions
from wokkel.xmppim import MessageProtocol, PresenceClientProtocol, RosterClientProtocol

class CompleteBotProtocol(MessageProtocol, RosterClientProtocol, PresenceClientProtocol):
    def __init__(self):
        self._parentInitializationFailed = None
    
    def connectionInitialized(self):
        MessageProtocol.connectionInitialized(self)
        RosterClientProtocol.connectionInitialized(self)
        PresenceClientProtocol.connectionInitialized(self)
    
    def connectionMade(self):
        self.available()
        d = self.getRoster()
        d.addCallback(self.onRosterReceived)
    
    def connectionLost(self, reason):
        print 'Connection Lost. Reason: %s'%(reason)
        #pass
    
    def initializationFailed(self, reason):
        print 'Initialization Failed. Reason: %s'%(reason)
        #pass
    
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
        pass
    
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
        pass
    
    def onRosterSet(self, item):
        pass
        
    def onRosterRemove(self, item):
        pass
    
    def onRosterReceived(self, roster):
        self.roster = roster
    
    def onMessage(self, msg):
        pass
    
