'''
Created on May 27, 2013

@author: pvicente
'''
from twisted.application import service
from twisted.internet import defer, reactor
from twisted.python import log
import cyclone.redis
import cyclone.web
import sys
from zope.interface import Interface, implements
from rq.job import Job

from utils.decorators import for_methods

@for_methods(['refresh'], defer.inlineCallbacks)
class TwistedJob(Job):
    pass

class RedisMixin(object):
    redis_conn = None

    @classmethod
    def setup(cls):
        # read settings from a conf file or something...
        cls.redis_conn = cyclone.redis.lazyConnectionPool()

class IWorkQueue(Interface):
    def getJob(self):
        """
        Return the current job
        """
        pass

class TWorkerService(service.Service, RedisMixin):
    implements(IWorkQueue)
    
    def __init__(self, queues):
        self.queues = queues
        self.stopped = False
        
    @defer.inlineCallbacks
    def getJob(self):
        try:
            job_id = yield self.redis_conn.blpop(keys=self.queues, timeout=1)
            print job_id
            if job_id:
                job = yield TwistedJob.fetch(job_id, self.redis_conn)
                print job
        except Exception as e:
            log.msg("Exception getting Job:", e)
        finally:
            if not self.stopped:
                reactor.callWhenRunning(self.getJob)

    def startService(self):
        reactor.callLater(1, self.getJob)
        service.Service.startService(self)

    def stopService(self):
        service.Service.stopService(self)
        self.stopped = True


