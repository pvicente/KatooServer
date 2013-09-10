'''
Created on Aug 7, 2013

@author: pvicente
'''
from applog import getLogger, getLoggerAdapter
from twisted.application import service
from twisted.internet import reactor, defer
from twisted.internet.protocol import ProcessProtocol
import os

log = getLogger(__name__, level='INFO')

class MultiProcessProtocol(ProcessProtocol):
    def __init__(self, parent):
        self.log = getLoggerAdapter(log, id=self.__class__.__name__)
        self.parent = parent
        self.parent.childs.append(self)
        self.ended = False
    
    def connectionMade(self):
        self.log.info("connectionMade!")
    
    def outReceived(self, data):
        self.log.info("outReceived! with %d bytes!\n%r", len(data), data)

    def errReceived(self, data):
        self.log.info("errReceived! with %d bytes!\n%r", len(data), data)
    
    def inConnectionLost(self):
        self.log.info("inConnectionLost! stdin is closed! (we probably did it)")
    
    def outConnectionLost(self):
        self.log.info("outConnectionLost! The child closed their stdout!")
    
    def errConnectionLost(self):
        self.log.info("errConnectionLost! The child closed their stderr")
    
    def processExited(self, reason):
        self.log.info("processExited, status %s", reason)
        self.ended = True
        if reactor.running:
            reactor.stop()
            self.log.warning('Stopped reactor due to child process exited')
    
    def processEnded(self, reason):
        self.log.info("processEnded, status %s", reason)
        self.ended = True
        if reactor.running:
            reactor.stop()
            self.log.warning('Stopped reactor due to child process ended')


class MultiProcess(service.Service):
    def __init__(self, pythontacfile, number=1, fds=[]):
        self.log = getLoggerAdapter(log, id=self.__class__.__name__)
        self.childFDs = dict([(0,0), (1,1), (2,2)] + [(fd,fd) for fd in fds])
        self.command = pythontacfile
        self.procnumbers = number
        self.childs = []
    
    @defer.inlineCallbacks
    def send_signal(self, signal):
        for child in self.childs:
            if not child.ended:
                self.log.info('Sending %s to child process', signal)
                yield child.transport.signalProcess(signal)
    
    def startService(self):
        service.Service.startService(self)
        self.log.info('Starting Service')
        for i in xrange(self.procnumbers):
            reactor.spawnProcess(MultiProcessProtocol(self), 'twistd', ['twistd', '-ny', self.command, '--pidfile=%s-%s.pid'%(self.command, i)], env=os.environ, childFDs=self.childFDs)
    
    def stopService(self):
        if self.running:
            service.Service.stopService(self)
            self.log.info('Stopping Service')
            self.send_signal('TERM')
    