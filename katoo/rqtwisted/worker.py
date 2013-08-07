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
import times
import traceback

DEFAULT_RESULT_TTL = 5
DEFAULT_WORKER_TTL = 420
TWISTED_WARMUP = 5

LOGGING_OK_JOBS = True
BASE_INCREMENT_CYCLES=25
NOJOB_INCREMET_CYCLES=200
TOP_CYCLES=400

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
        self._processedJobs = 0
        self._cycles = 0
        self._increment_cycles=BASE_INCREMENT_CYCLES
    
    @classmethod
    @defer.inlineCallbacks
    def getWorkers(cls, key, connection = None):
        if connection is None:
            connection = RedisMixin.redis_conn
        names = yield connection.smembers(key)
        workers = []
        for name in names:
            worker = yield connection.hgetall(name)
            worker['key'] = name
            worker['name'] = name.split(':')[-1]
            workers.append(worker)
        defer.returnValue(workers)
    
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
        self.log.msg('REGISTER_BIRTH of worker %s' % (self.name,))
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
        self.log.msg('REGISTER_DEATH of worker %s'%(self.name))
        d1 = self.connection.srem(self.redis_workers_keys, self.key)
        d2 = self.setDeath(self.key, datetime.utcnow(), connection=self.connection)
        d3 = self.connection.sadd(self.redis_death_workers_keys, self.key)
        
        ret = defer.DeferredList([d1,d2,d3], consumeErrors=True)
        return ret
    
    @defer.inlineCallbacks
    def is_alive(self):
        exists = True
        death = yield self.connection.hget(self.key, 'death')
        if death is None:
            exists  = yield self.connection.exists(self.key)
        ret = bool(exists and death is None)
        defer.returnValue(ret)

    
    @classmethod
    def setDeath(cls, key, value, connection=None):
        if connection is None:
            connection = RedisMixin.redis_conn
        return connection.hset(key, 'death', value)
    
    @property
    def lastTime(self):
        return self._lastTime
    
    def set_lastTime(self, value):
        delta = value - self._lastTime
        seconds = delta.seconds
        if seconds > 2:
            jobs = (self._processedJobs*1.0)/seconds if seconds > 0 else self._processedJobs*1.0
            self._processedJobs = 0
            self.log.msg('REFRESH_LAST_TIME %s second(s) ago. %.2f jobs/second'%(seconds, jobs))
            self._lastTime = value
            return self.connection.hset(self.key, 'lastTime', self._lastTime)
    
    def cycles_inc(self, job=True):
        if job:
            self._increment_cycles/=2
            self._cycles+=self._increment_cycles or 1
            self._processedJobs+=1
        else:
            self._increment_cycles = BASE_INCREMENT_CYCLES
            self._cycles+=NOJOB_INCREMET_CYCLES
        
        if self._cycles>=TOP_CYCLES:
            self._cycles = 0
            self.set_lastTime(datetime.utcnow())
    
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
        
        meta = ','.join([item for item in job.meta.values()])
        job.meta['failure'] = failure
        self.log.msg('[%s] JOB_FAILED %s: %s'%(meta, job, exc_string))
        yield self.failed_queue.quarantine(job, exc_info=exc_string)
    
    @defer.inlineCallbacks
    def work(self):
        yield self.set_state('starting')
        connection_errors = 0
        alive = True
        while not self.stopped and alive:
            res = job = None
            try:
                yield self.set_state('idle')
                
                alive = yield self.is_alive()
                if not alive and reactor.running:
                    self.log.err('Worker is not ALIVE. Stopping reactor ...')
                    reactor.stop()
                    continue
                
                res = yield Queue.dequeue_any(queue_keys=self.queue_keys(), timeout=self.blocking_time, connection=self.connection)
                connection_errors = 0
                if res is None:
                    self.cycles_inc(job=False)
                    continue
                
                self.cycles_inc()
                
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
        yield self.move_to_failed_queue(job, failure=failure)
    
    @defer.inlineCallbacks
    def callback_perform_job(self, result):
        rv, job = result
        if isinstance(rv, defer.Deferred):
            rv = yield rv
        pickled_rv = dumps(rv)
        job._status = Status.FINISHED
        job.ended_at = times.now()
        
        if LOGGING_OK_JOBS:
            meta = ','.join([item for item in job.meta.values()])
            if rv is None:
                self.log.msg('[%s] Job OK. %s'%(meta, job))
            else:
                self.log.msg('[%s] Job OK. %s. result = %r' % (meta, job, rv))
        
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
        service.Service.startService(self)
        reactor.callLater(self.default_warmup, self.register_birth)
        for _ in xrange(self.loops):
            reactor.callLater(self.default_warmup+1, self.work)

    def stopService(self):
        service.Service.stopService(self)
        self._stopped = True
        return self.register_death()