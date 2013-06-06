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
from katoo import conf
from wokkel.xmppim import MessageProtocol, PresenceClientProtocol, \
    RosterClientProtocol

class CompleteBotProtocol(MessageProtocol, RosterClientProtocol, PresenceClientProtocol):
    ROSTER_IN_MEMORY = conf.XMPP_ROSTER_IN_MEMORY
    def __init__(self):
        self._parentInitializationFailed = None
    
    def connectionInitialized(self):
        #print '(%s) Connection Initialized'%(hex(id(self)))
        MessageProtocol.connectionInitialized(self)
        RosterClientProtocol.connectionInitialized(self)
        PresenceClientProtocol.connectionInitialized(self)
        
        #Send Available and getting roster
        self.available()
        d = self.getRoster()
        d.addCallback(self.onRosterReceived)
    
    def connectionMade(self):
        #print '(%s) Connection Made'%(hex(id(self)))
        self.parent.onAuthError = self.onAuthError
    
    def connectionLost(self, reason):
        #print '(%s) Connection Lost. Reason: %s'%(hex(id(self)), reason)
        pass
    
    def onAuthError(self, reason):
        #print '(%s) onAuthError. Reason: %s'%(hex(id(self)), reason)
        pass
        
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
        #print 'Available received. %s'%(locals())
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
        #print 'Unavailable received. %s'%(locals())
        pass
    
    def onRosterSet(self, item):
        pass
        
    def onRosterRemove(self, item):
        pass
    
    def onRosterReceived(self, roster):
        print '(%s) onRosterReceived: %s'%(hex(id(self)), roster)
        self.roster = roster
    
    def onMessage(self, msg):
        pass
        #if msg['type'] == 'chat' and not msg.body is None:
            #print '(%s) onMessage: %s'%(hex(id(self)), msg.body)
    
