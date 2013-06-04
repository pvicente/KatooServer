'''
Created on Jun 2, 2013

@author: pvicente
'''
from katoo.rqtwisted.queue import Queue, FailedQueue
from katoo.utils.redis import RedisMixin
from pickle import dumps
from rq.exceptions import NoQueueError
from rq.job import Status
from rq.utils import make_colorizer
from twisted.application import service
from twisted.internet import defer, threads, reactor
from twisted.python import log
import os
import platform
import random
import rq.worker
import sys
import time
import times
import traceback

DEFAULT_RESULT_TTL = 5
DEFAULT_WORKER_TTL = 420

green = make_colorizer('darkgreen')
yellow = make_colorizer('darkyellow')
blue = make_colorizer('darkblue')

class Worker(service.Service, RedisMixin, rq.worker.Worker):
    def __init__(self, queues, name=None, 
        default_result_ttl=DEFAULT_RESULT_TTL, connection=None, 
        exc_handler=None, default_worker_ttl=DEFAULT_WORKER_TTL):
        if connection is None:
            connection = RedisMixin.redis_conn
        self.connection = connection
        if isinstance(queues, Queue):
            queues = [queues]
        self._name = name
        self.queues = queues
        self.validate_queues()
        self._exc_handlers = []
        self.default_result_ttl = default_result_ttl
        self.default_worker_ttl = default_worker_ttl
        self._state = 'starting'
        self._is_horse = False
        self._horse_pid = 0
        self._stopped = False
        self.log = log
        self.failed_queue = FailedQueue(connection=self.connection)
        self.blocking_time = 1
    
    @classmethod
    def default_name(cls):
        return '%.3f-%s.%s' % (random.random(), platform.node(), os.getpid())
    
    @classmethod
    @defer.inlineCallbacks
    def all(cls, connection=None):
        if connection is None:
            connection = RedisMixin.redis_conn
        yield super(Worker, cls).all(connection=connection)
    
    @classmethod
    @defer.inlineCallbacks
    def find_by_key(cls, worker_key, connection=None):
        if connection is None:
            connection = RedisMixin.redis_conn
        yield super(Worker, cls).find_by_key(worker_key, connection=connection)
    
    @defer.inlineCallbacks
    def register_birth(self):  # noqa
        """Registers its own birth."""
        self.log.msg('Registering birth of worker %s' % (self.name,))
        exist_key = yield self.connection.exists(self.key)
        death =  yield self.connection.hexists(self.key, 'death')
        if exist_key and not death:
            raise ValueError(
                    'There exists an active worker named \'%s\' '
                    'already.' % (self.name,))
        key = self.key
        now = time.time()
        queues = ','.join(self.queue_names())
        yield self.connection.delete(key)
        yield self.connection.hset(key, 'birth', now)
        yield self.connection.hset(key, 'queues', queues)
        yield self.connection.sadd(self.redis_workers_keys, key)
#        yield t.expire(key, self.default_worker_ttl)
    
    def register_death(self):
        """Registers its own death."""
        self.log.msg('Registering death of worker', self.name)
        d1 = self.connection.srem(self.redis_workers_keys, self.key)
        d2 = self.connection.hset(self.key, 'death', time.time())
        
        #TODO: It will be removed when workers will registered in death set. Issue #6
        d3 = self.connection.expire(self.key, 5)
        ret = defer.DeferredList([d1,d2,d3], consumeErrors=True)
        return ret
    
    @property
    def state(self):
        return self._state
    
    def set_state(self, new_state):
        if self._state != new_state:
            self._state = new_state
            return self.connection.hset(self.key, 'state', new_state)
        return defer.succeed(None)
    
    @property
    def name(self):
        if self._name is None:
            self._name = self.default_name()
        return self._name
    
    def queue_names(self):
        """Returns the queue names of this worker's queues."""
        return [q.name for q in self.queues]
    
    def queue_keys(self):
        """Returns the Redis keys representing this worker's queues."""
        return [q.key for q in self.queues]
    
    def validate_queues(self):  # noqa
        """Sanity check for the given queues."""
        if not hasattr(self.queues, '__iter__'):
            raise ValueError('Argument queues not iterable.')
        final_queue = []
        for queue in self.queues:
            if isinstance(queue, str):
                queue = Queue(name=queue, connection=self.connection)
            elif not isinstance(queue, Queue):
                raise NoQueueError('Give each worker at least one Queue.')
            final_queue.append(queue)
        self.queues = final_queue

    def move_to_failed_queue(self, job, *exc_info,**kwargs ):
        """Default exception handler: move the job to the failed queue."""
        failure = kwargs.get('failure')
        if failure is None:
            exc_string = ''.join(traceback.format_exception(*exc_info))
        else:
            exc_string = failure.getTraceback()
        return self.failed_queue.quarantine(job, exc_info=exc_string)
    
    @defer.inlineCallbacks
    def work(self):
        yield self.set_state('starting')
        while not self.stopped:
            res = job = None
            try:
                yield self.set_state('idle')
                res = yield Queue.dequeue_any(queue_keys=self.queue_keys(), timeout=self.blocking_time, connection=self.connection)
                if res is None:
                    continue
                yield self.set_state('busy')
                queue_key, job = res
                d = threads.deferToThread(job.perform)
                d.addCallback(self.callback_perform_job)
                d.addErrback(self.errback_perform_job, job=job)
            except Exception as e:
                log.msg('Exception %s dequeing job %s:'%(e.__class__.__name__, str(job)), e)
                if not job is None:
                    job.status = Status.FAILED
                    self.move_to_failed_queue(job, *sys.exc_info())
    
    def errback_perform_job(self, failure, job):
        self.log.msg('errback perform job: %s. Failure: %s'%(job, failure))
        job.status = Status.FAILED
        return self.move_to_failed_queue(job, failure=failure)
    
    @defer.inlineCallbacks
    def callback_perform_job(self, result):
        rv, job = result
        pickled_rv = dumps(rv)
        job._status = Status.FINISHED
        job.ended_at = times.now()
#             if rv is None:
#                 self.log.msg('Job OK')
#             else:
#                 self.log.msg('Job OK, result = %s' % (yellow(unicode(rv)),))
        result_ttl =  self.default_result_ttl if job.result_ttl is None else job.result_ttl
        if result_ttl == 0:
            yield job.delete()
            #self.log.msg('Result discarded immediately.')
        else: 
            yield self.connection.hset(job.key, 'result', pickled_rv)
            yield self.connection.hset(job.key, 'ended_at', times.format(job.ended_at, 'UTC'))
            yield self.connection.hset(job.key, 'status', job._status)
            if result_ttl > 0:
                yield self.connection.expire(job.key, result_ttl)
    
    def startService(self):
        reactor.callLater(1, self.register_birth)
        reactor.callLater(2, self.work)
        service.Service.startService(self)

    def stopService(self):
        self._stopped = True
        service.Service.stopService(self)
        return self.register_death()