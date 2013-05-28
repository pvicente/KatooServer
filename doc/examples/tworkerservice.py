'''
Created on May 27, 2013

@author: pvicente
'''
from katoo.rqtwisted import RedisMixin, RQTwistedJob, RQTwistedQueue
from twisted.application import service
from twisted.internet import defer, reactor, threads
from twisted.python import log
from zope.interface import Interface, implements
from time import time

class IWorkQueue(Interface):
    def getJob(self):
        """
        Return the current job
        """
        pass

last_time = time()
last_processed = 0

def example_func(argument):
    if argument%1000 == 0:
        global last_time, last_processed
        current_time = time()
        per_second = (argument - last_processed)/(current_time - last_time)
        last_time, last_processed = current_time, argument
        log.msg('Processed jobs: %s/s. Total: %s '%(per_second, argument))


class TEnqueingService(service.Service, RedisMixin):
    def __init__(self, queue_name, sleep_time):
        self.queue = RQTwistedQueue(name=queue_name)
        self.sleep_time = sleep_time
        self.enqueued = 0
        self.stopped = False
    
    @defer.inlineCallbacks
    def enqueue(self):
        try:
            yield self.queue.enqueue_call(func=example_func, args=(self.enqueued,))
            self.enqueued+=1
        except Exception as e:
            log.msg('Exception enqueing:', e)
            raise
        finally:
            if not self.stopped:
                reactor.callLater(self.sleep_time, self.enqueue)

    def startService(self):
        reactor.callLater(1, self.enqueue)
        service.Service.startService(self)

    def stopService(self):
        service.Service.stopService(self)
        self.stopped = True


class TDequeingService(service.Service, RedisMixin):
    def __init__(self, queue_name, blocking_time):
        self.queue = RQTwistedQueue(name=queue_name)
        self.blocking_time = blocking_time
        self.stopped = False
    
    @defer.inlineCallbacks
    def dequeue(self):
        try:
            job = yield self.queue.dequeue(self.blocking_time)
            if not job is None:
                threads.deferToThread(job.perform)
        except Exception as e:
            log.msg('Exception dequeing:', e)
            raise
        finally:
            if not self.stopped:
                reactor.callWhenRunning(self.dequeue)
    
    def startService(self):
        reactor.callLater(1, self.dequeue)
        service.Service.startService(self)

    def stopService(self):
        service.Service.stopService(self)
        self.stopped = True
    
    

class TQueuesService(service.Service, RedisMixin):
    def __init__(self, queues):
        self.queues = [RQTwistedQueue(name) for name in queues]
        self.queue_keys = [q.key for q in self.queues]
        self.stopped = False
        self.processed = 0
    
    @defer.inlineCallbacks
    def dequeue_any(self):
        try:
            res = yield RQTwistedQueue.dequeue_any(queue_keys=self.queue_keys, timeout=1, connection=RedisMixin.redis_conn)
            if not res is None:
                queue, job = res
                log.msg('Fetched job:%s from queue:%s'%(job, queue))
                threads.deferToThread(job.perform)
        except Exception as e:
            log.msg('Exception dequeing:', e)
            raise e
        finally:
            if not self.stopped:
                reactor.callWhenRunning(self.dequeue_any)
    @defer.inlineCallbacks
    def dequeue2(self):
        try:
            queue = self.queues[0]
            job = yield queue.dequeue(timeout=1)
            if not job is None:
                log.msg('Fetched job:%s from queue:%s'%(job, queue))
                job.perform()
        except Exception as e:
            log.msg('Exception dequeing:', e)
            raise
        finally:
            if not self.stopped:
                reactor.callWhenRunning(self.dequeue2)
        
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
            yield queue.enqueue_call(func=example_func, args=(self.processed,))
            self.processed+=1
            #log.msg('Enqueued:', res)
        except Exception as e:
            log.msg('Exception enqueing:', e)
            raise
        finally:
            if not self.stopped:
                reactor.callLater(0.001, self.enqueue)
    
    def startService(self):
        reactor.callLater(1, self.dequeue_any)
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
            reactor.callWhenRunning(self.addJob)
        
    def startService(self):
        reactor.callLater(1, self.getJob)
        reactor.callLater(5, self.addJob)
        service.Service.startService(self)

    def stopService(self):
        service.Service.stopService(self)
        self.stopped = True


