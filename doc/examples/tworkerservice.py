'''
Created on May 27, 2013

@author: pvicente
'''
from katoo.rqtwisted.job import Job, UnpickleError, NoSuchJobError
from katoo.rqtwisted.queue import Queue
from katoo.utils.redis import RedisMixin
from time import time, sleep
from twisted.application import service
from twisted.internet import defer, reactor, threads
from twisted.python import log
from zope.interface import Interface, implements
from katoo.rqtwisted import job

class IWorkQueue(Interface):
    def getJob(self):
        """
        Return the current job
        """
        pass

last_time = time()
last_processed = 0

def print_stats(argument, summary, last_time, last_processed):
        current_time = time()
        per_second = (argument - last_processed)/(current_time - last_time)
        last_time, last_processed = current_time, argument
        log.msg('%s: %s/s. Total: %s '%(summary, per_second, argument))
        return last_time, last_processed

def example_func(argument):
    global last_time, last_processed
    #sleep(5)
    if argument%1000 == 0:
        last_time, last_processed = print_stats(argument, 'Processed jobs', last_time, last_processed)

class TEnqueingService(service.Service, RedisMixin):
    def __init__(self, queue_name, sleep_time):
        self.queue = Queue(name=queue_name)
        self.sleep_time = sleep_time
        self.stopped = False
        self.enqueued = 0
        self.last_time = time()
        self.last_processed = 0

    def callback_enqueue(self, data):
        self.enqueued+=1
        if self.enqueued%1000 == 0:
            self.last_time, self.last_processed = print_stats(self.enqueued, 'Enqueued jobs', self.last_time, self.last_processed)
        
    def enqueue(self):
        try:
            d = self.queue.enqueue_call(func=example_func, args=(self.enqueued,))
            d.addCallback(self.callback_enqueue)
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

class TOfflineDequeingService(service.Service, RedisMixin):
    def __init__(self, queue_name, timeout):
        self.queue = Queue(name=queue_name)
        self.timeout = timeout
        self.stopped = False
    
    def callback_perform(self, result):
        if not self.stopped:
            reactor.callWhenRunning(self.dequeue)
    
    def callback_dequeue(self, job):
        if not job is None:
            d = threads.deferToThread(job.perform)
            d.addCallback(self.callback_perform)
            return d
        if not self.stopped:
            reactor.callWhenRunning(self.dequeue)
        return defer.succeed(None)
    
    def dequeue(self):
        d = self.queue.dequeue(self.timeout)
        d.addCallback(self.callback_dequeue)
    
    def startService(self):
        reactor.callLater(1, self.dequeue)
        service.Service.startService(self)
    
    def stopService(self):
        service.Service.stopService(self)
        self.stopped = False
    
class TInlineDequeingService(service.Service, RedisMixin):
    def __init__(self, queue_name, blocking_time):
        self.queue = Queue(name=queue_name)
        self.blocking_time = blocking_time
        self.stopped = False
    
    @defer.inlineCallbacks
    def dequeue(self):
        while not self.stopped:
            try:
                job = yield self.queue.dequeue(self.blocking_time)
                if not job is None:
                    yield threads.deferToThread(job.perform)
            except (UnpickleError, NoSuchJobError) as e:
                log.msg('Exception %s fetching job'%(e.__class__.__name__), e)                
            except Exception as e:
                log.msg('Exception %s dequeing job %s:'%(e.__class__.__name__, str(job)), e)
                raise
    
    def startService(self):
        reactor.callLater(1, self.dequeue)
        service.Service.startService(self)

    def stopService(self):
        service.Service.stopService(self)
        self.stopped = True
    
    

class TQueuesService(service.Service, RedisMixin):
    def __init__(self, queues):
        self.queues = [Queue(name) for name in queues]
        self.queue_keys = [q.key for q in self.queues]
        self.stopped = False
        self.processed = 0
    
    @defer.inlineCallbacks
    def dequeue_any(self):
        try:
            res = yield Queue.dequeue_any(queue_keys=self.queue_keys, timeout=1, connection=RedisMixin.redis_conn)
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
            res = yield Queue.lpop(self.queue_keys, timeout=1, connection=self.redis_conn)
            if res is None:
                return
            queue_key, job_id = res
            log.msg('Job: %s in queue: %s'%(job_id, queue_key))
            job = yield Job.fetch(job_id, connection=self.redis_conn)
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
            queue = Queue()
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
            exists = yield Job.exists(job_id)
            print "Job: %s exists %s"%(job_id, exists)
            job = yield Job.fetch(job_id)
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
        job = Job.create(func=example_func, args=(3,))
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


