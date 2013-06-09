'''
Created on Jun 9, 2013

@author: pvicente
'''

class GenericXMPPHandler(object):
    
    def __init__(self, client):
        self.client = client
        self.protocol = None
    
    def setProtocol(self, protocol):
        self.protocol = protocol
    
    def onConnectionEstablished(self):
        pass
    
    def onAuthenticated(self):
        pass
    
    def onConnectionLost(self, reason):
        pass
    
    def onAvailableReceived(self, jid):
        pass
    
    def onUnavailableReceived(self, jid):
        pass
    
    def onRosterSet(self, item):
        pass
    
    def onRosterRemove(self, item):
        pass
    
    def onRosterReceived(self, roster):
        pass
    
    def onMessageReceived(self, msg):
        pass
    