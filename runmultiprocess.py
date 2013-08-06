'''
Created on Aug 6, 2013

@author: pvicente
'''

from twisted.application import service
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol
import os

class MultiProcessProtocol(ProcessProtocol):
    def connectionMade(self):
        print "connectionMade!"
    def outReceived(self, data):
        print "outReceived! with %d bytes!" % len(data)
        print data
    def errReceived(self, data):
        print "errReceived! with %d bytes!" % len(data)
        print data
        print repr(data)
    
    def inConnectionLost(self):
        print "inConnectionLost! stdin is closed! (we probably did it)"
    def outConnectionLost(self):
        print "outConnectionLost! The child closed their stdout!"
    def errConnectionLost(self):
        print "errConnectionLost! The child closed their stderr."
    def processExited(self, reason):
        print "processExited, status %d" % (reason.value.exitCode,)
    def processEnded(self, reason):
        print "processEnded, status %d" % (reason.value.exitCode,)
        print "quitting"
        reactor.stop()

class MultiProcess(service.Service):
    def __init__(self):
        self.protocol = MultiProcessProtocol()
        self.childs = []
        
    def startService(self):
        for _ in xrange(2):
            self.childs.append(reactor.spawnProcess(self.protocol, 'twistd', ['twistd', '-ny', 'runxmpp.py', '--pidfile=xmpp.pid'], env=os.environ, childFDs={0:0, 1:1, 2:2}))
    
    def stopService(self):
        for child in self.childs:
            child.signalProcess('KILL')

application = service.Application('KatooAppMultiProcess')

m = MultiProcess()
m.setServiceParent(application)


