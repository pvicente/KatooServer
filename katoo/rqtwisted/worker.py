'''
Created on Jun 2, 2013

@author: pvicente
'''
from datetime import datetime
from katoo.utils.connections import \
    RedisMixin #TODO: Pending to remove RedisMixin object from katoo
from pickle import dumps
from queue import Queue, FailedQueue
from rq.exceptions import NoQueueError
from rq.job import Status
from rq.utils import make_colorizer
from twisted.application import service
from twisted.internet import defer, threads, reactor
from twisted.python import log
from twisted.python.failure import Failure
import cyclone.redis
import os
import platform
import rq.worker
import sys
import time
import times
import traceback

DEFAULT_RESULT_TTL = 5
DEFAULT_WORKER_TTL = 420
TWISTED_WARMUP = 5

green = make_colorizer('darkgreen')
yellow = make_colorizer('darkyellow')
blue = make_colorizer('darkblue')

class Worker(service.Service, RedisMixin, rq.worker.Worker):
    redis_death_workers_keys = "rq:workers:death"
    def __init__(self, queues, name=None, loops = 1, blocking_time = 1,
        default_result_ttl=DEFAULT_RESULT_TTL, connection=None, 
        exc_handler=None, default_worker_ttl=DEFAULT_WORKER_TTL, default_warmup=TWISTED_WARMUP):
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
        self.blocking_time = blocking_time
        self.loops = loops
        self.default_warmup = default_warmup
        self._lastTime = datetime.utcnow()
    
    @classmethod
    @defer.inlineCallbacks
    def deathWorkers(cls):
        connection = RedisMixin.redis_conn
        death_workers_names = yield connection.smembers(cls.redis_death_workers_keys)
        death_workers = []
        for worker_name in death_workers_names:
            worker = yield connection.hgetall(worker_name)
            worker['key'] = worker_name
            worker['name'] = worker_name.split(':')[-1]
            death_workers.append(worker)
        defer.returnValue(death_workers)
    
    @classmethod
    @defer.inlineCallbacks
    def remove(cls, key):
        connection = RedisMixin.redis_conn
        yield connection.srem(cls.redis_workers_keys, key)
        yield connection.srem(cls.redis_death_workers_keys, key)
        yield connection.expire(key, 1)
    
    @classmethod
    def default_name(cls):
        return '%s.%s' % (platform.node(), os.getpid())
    
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
        queues = ','.join(self.queue_names())
        now =  datetime.utcnow()
        yield self.connection.delete(key)
        yield self.connection.hset(key, 'birth', now)
        yield self.connection.hset(key, 'queues', queues)
        yield self.connection.hset(key, 'lastTime', now)
        yield self.connection.sadd(self.redis_workers_keys, key)
    
    def register_death(self):
        """Registers its own death."""
        self.log.msg('Registering death of worker %s'%(self.name))
        d1 = self.connection.srem(self.redis_workers_keys, self.key)
        d2 = self.connection.hset(self.key, 'death', datetime.utcnow())
        d3 = self.connection.sadd(self.redis_death_workers_keys, self.key)
        
        ret = defer.DeferredList([d1,d2,d3], consumeErrors=True)
        return ret
    
    def is_death(self):
        return self.connection.hget(self.key, 'death')
        
    @property
    def lastTime(self):
        return self._lastTime
    
    def set_lastTime(self, value):
        self._lastTime = value
        return self.connection.hset(self.key, 'lastTime', self.lastTime)
    
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
    
    @defer.inlineCallbacks
    def move_to_failed_queue(self, job, *exc_info,**kwargs ):
        """Default exception handler: move the job to the failed queue."""
        failure = kwargs.get('failure')
        if failure is None:
            failure = Failure(exc_info[0], exc_info[1], exc_info[2])
            exc_string = ''.join(traceback.format_exception(*exc_info))
        else:
            exc_string = failure.getTraceback()
        job.meta['failure'] = failure
        yield self.failed_queue.quarantine(job, exc_info=exc_string)
    
    @defer.inlineCallbacks
    def work(self):
        yield self.set_state('starting')
        connection_errors = 0
        death = None
        cycles = 0
        while not self.stopped and death is None:
            res = job = None
            try:
                if cycles % 500 == 0:
                    #every 10 seconds when idle lastTime is updated
                    cycles = 0
                    yield self.set_lastTime(datetime.utcnow())

                yield self.set_state('idle')
                
                death = yield self.is_death()
                if not death is None and reactor.running:
                    self.log.err('Worker tagged as DEATH. Stopping reactor ...')
                    reactor.stop()
                    continue
                
                res = yield Queue.dequeue_any(queue_keys=self.queue_keys(), timeout=self.blocking_time, connection=self.connection)
                connection_errors = 0
                if res is None:
                    cycles+=100
                    continue
                
                cycles+=1
                
                yield self.set_state('busy')
                
                #Parameter _ is queue_key must be a processed when thresholds will be implemented
                _, job = res
                d = threads.deferToThread(job.perform)
                d.addCallback(self.callback_perform_job)
                d.addErrback(self.errback_perform_job, job=job)
                
            except cyclone.redis.ConnectionError as e:
                self.log.err(e, 'REDIS_CONNECTION_ERROR')
                connection_errors += 1
                if connection_errors >= 3:
                    self._stopped = True
                    self.log.msg('Exiting due too many connection errors (%s) with redis'%(connection_errors))
                    if reactor.running:
                        reactor.stop()
            except Exception as e:
                self.log.err(e, 'UNKNOWN_EXCEPTION')
                if not job is None:
                    job.status = Status.FAILED
                    yield self.move_to_failed_queue(job, *sys.exc_info())
    
    @defer.inlineCallbacks
    def errback_perform_job(self, failure, job):
        #TODO: Remove log
        self.log.err(failure, 'PERFORM_JOB %s'%(job))
        yield self.move_to_failed_queue(job, failure=failure)
    
    @defer.inlineCallbacks
    def callback_perform_job(self, result):
        rv, job = result
        if isinstance(rv, defer.Deferred):
            rv = yield rv
        pickled_rv = dumps(rv)
        job._status = Status.FINISHED
        job.ended_at = times.now()
        
        #TODO: Remove log
        if rv is None:
            self.log.msg('[%s] Job OK'%(job))
        else:
            self.log.msg('[%s] Job OK, result = %r' % (job, rv))
        
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
        reactor.callLater(self.default_warmup, self.register_birth)
        for _ in xrange(self.loops):
            reactor.callLater(self.default_warmup+1, self.work)
        service.Service.startService(self)

    def stopService(self):
        self._stopped = True
        service.Service.stopService(self)
        return self.register_death()