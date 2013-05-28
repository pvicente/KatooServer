'''
Created on May 27, 2013

@author: pvicente
'''
from katoo.rqtwisted import RedisMixin, RQTwistedJob, RQTwistedQueue
from twisted.application import service
from twisted.internet import defer, reactor, threads
from twisted.python import log
from zope.interface import Interface, implements

class IWorkQueue(Interface):
    def getJob(self):
        """
        Return the current job
        """
        pass

def example_func(argument):
    print 'Hello', argument

class TQueueService(service.Service, RedisMixin):
    def __init__(self, queues):
        self.queues = [RQTwistedQueue(name) for name in queues]
        self.queue_keys = [q.key for q in self.queues]
        self.stopped = False
        
    @defer.inlineCallbacks
    def dequeue(self):
        try:
            res = yield RQTwistedQueue.lpop(self.queue_keys, timeout=1, connection=self.redis_conn)
            if res is None:
                return
            queue_key, job_id = res
            log.msg('Job: %s in queue: %s'%(job_id, queue_key))
            job = yield RQTwistedJob.fetch(job_id, connection=self.redis_conn)
            if not job is None:
                log.msg('Fetch Job:', job)
                job.perform()
        except Exception as e:
            log.msg('Exception dequeing:', e)
            raise
        finally:
            if not self.stopped:
                reactor.callWhenRunning(self.dequeue)
    
    @defer.inlineCallbacks
    def enqueue(self):
        try:
            queue = RQTwistedQueue()
            res = yield queue.enqueue_call(func=example_func, args=(1,))
            log.msg('Enqueued:', res)
            print res
        except Exception as e:
            log.msg('Exception enqueing:', e)
            raise
        finally:
            if not self.stopped:
                reactor.callLater(1, self.enqueue)
    
    def startService(self):
        reactor.callLater(1, self.dequeue)
        reactor.callLater(5, self.enqueue)
        service.Service.startService(self)

    def stopService(self):
        service.Service.stopService(self)
        self.stopped = True

class TWorkerService(service.Service, RedisMixin):
    implements(IWorkQueue)
    
    def __init__(self, queues):
        self.queue = []
        self.stopped = False
    
    @defer.inlineCallbacks
    def getJob(self):
        try:
            job_id = self.queue.pop()
            exists = yield RQTwistedJob.exists(job_id)
            print "Job: %s exists %s"%(job_id, exists)
            job = yield RQTwistedJob.fetch(job_id)
            status = yield job.status
            print job, status
            yield threads.deferToThread(job.perform)
            status = yield job.status
            print job, status
        except Exception as e:
            log.msg("Exception getting Job:", e)
        finally:
            if not self.stopped:
                reactor.callWhenRunning(self.getJob)

    @defer.inlineCallbacks
    def addJob(self):
        job = RQTwistedJob.create(func=example_func, args=(3,))
        print 'Adding job:', job 
        yield job.save()
        self.queue.append(job.id)
        if not self.stopped:
            reactor.callLater(1, self.addJob)
        
    def startService(self):
        reactor.callLater(5, self.getJob)
        reactor.callLater(1, self.addJob)
        service.Service.startService(self)

    def stopService(self):
        service.Service.stopService(self)
        self.stopped = True


