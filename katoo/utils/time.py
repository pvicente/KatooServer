'''
Created on Jul 5, 2013

@author: pvicente
'''
from datetime import datetime
from katoo import conf
from patterns import Singleton
from twisted.application import service
from twisted.internet import defer, reactor
from twisted.internet.task import LoopingCall
from katoo.utils.applog import getLoggerAdapter, getLogger

def sleep(secs):
    d = defer.Deferred()
    reactor.callLater(secs, d.callback, None)
    return d

class Timer(service.Service, Singleton):
    def constructor(self):
        self._time = datetime.utcnow()
        self.log = getLoggerAdapter(getLogger(__name__, "INFO"), id='TIMER')
        self._interval = conf.TIMER_INTERVAL
        self._maxinterval = self._interval*3
    
    def _updateTime(self):
        last_time = self._time
        self._time = datetime.utcnow()
        elapsed = self._time - last_time
        if elapsed.seconds > self._maxinterval:
            self.log.warning('Timer not too much accurate. Elapsed %s seconds without update', elapsed.seconds)
    
    def startService(self):
        self.log.info('Started Timer')
        self._task= LoopingCall(self._updateTime)
        self._task.start(self._interval, now=False)
        return service.Service.startService(self)
    
    def stopService(self):
        if self.running:
            self._task.stop()
            self.log.info('Stopped Timer')
        return service.Service.stopService(self)
    
    def utcnow(self):
        return self._time