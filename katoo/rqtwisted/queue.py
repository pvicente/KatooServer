'''
Created on Jun 2, 2013

@author: pvicente
'''
from functools import total_ordering
from katoo.rqtwisted.job import Job
from katoo.utils.connections import RedisMixin
from rq.exceptions import NoSuchJobError, UnpickleError
from rq.job import Status
from twisted.internet import defer
import rq
import times

@total_ordering
class Queue(rq.queue.Queue):
    @classmethod
    def all(cls, connection=None):
        """Returns an iterable of all Queues.
        """
        prefix = cls.redis_queue_namespace_prefix
        
        if connection is None:
            connection = RedisMixin.redis_conn
        def to_queue(queue_key):
            return cls.from_queue_key(queue_key)
        d = connection.keys('%s*' % prefix)
        d.addCallback(lambda keys: map(to_queue, keys))
        return d

    @classmethod
    def from_queue_key(cls, queue_key, connection=None):
        """Returns a Queue instance, based on the naming conventions for naming
        the internal Redis keys.  Can be used to reverse-lookup Queues by their
        Redis keys.
        """
        prefix = cls.redis_queue_namespace_prefix
        if not queue_key.startswith(prefix):
            raise ValueError('Not a valid RQ queue key: %s' % (queue_key,))
        name = queue_key[len(prefix):]
        return cls(name)

    def __init__(self, name='default', default_timeout=None, connection=None,
                 async=True):
        if connection is None:
            connection = RedisMixin.redis_conn
        self.connection = connection
        prefix = self.redis_queue_namespace_prefix
        self.name = name
        self._key = '%s%s' % (prefix, name)
        self._default_timeout = default_timeout
        self._async = True

    def empty(self):
        """Removes all messages on the queue."""
        return self.connection.delete(self.key)
    
    def is_empty(self):
        """Returns whether the current queue is empty."""
        return self.count.addCallback(lambda x: x == 0)

    @property
    def count(self):
        """Returns a count of all messages in the queue."""
        return self.connection.llen(self.key)
    
    @property
    def job_ids(self):
        """Returns a list of all job IDS in the queue."""
        return self.connection.lrange(self.key, 0, -1)

    @property
    def jobs(self):
        """Returns all jobs from queue and remove jobs with errors when fetch is performed"""
        
        def get_jobs(job_ids):
            return defer.DeferredList([Job.safe_fetch(job_id, self.connection) for job_id in job_ids], consumeErrors=True)
        
        def compact(deferred_list):
            ret = []
            for job in deferred_list:
                if isinstance(job, Job):
                    ret.append(job)
                else:
                    self.remove(job.job_id)
            return ret
        
        d = self.job_ids
        d.addCallback(get_jobs)
        d.addCallback(compact)
        return d

    def remove(self, job_or_id):
        """Removes Job from queue, accepts either a Job instance or ID."""
        job_id = job_or_id.id if isinstance(job_or_id, Job) else job_or_id
        self.connection.lrem(self.key, 0, job_id)
        return defer.succeed(job_or_id)
    
    def compact(self):
        raise NotImplemented()
    
    def push_job(self, job):  # noqa
        """Pushes a job ID on the corresponding Redis queue."""
        return self.connection.rpush(self.key, job.id)
    
    @defer.inlineCallbacks
    def pop_job_id(self):
        """Pops a given job ID from this Redis queue."""
        ret = yield self.connection.lpop(self.key)
        defer.returnValue(ret)
    

    @defer.inlineCallbacks
    def enqueue_call(self, func, args=None, kwargs=None, timeout=None, result_ttl=None): #noqa
        """Creates a job to represent the delayed function call and enqueues
        it.

        It is much like `.enqueue()`, except that it takes the function's args
        and kwargs as explicit arguments.  Any kwargs passed to this function
        contain options for RQ itself.
        """
        timeout = timeout or self._default_timeout
        job = Job.create(func, args, kwargs, connection=self.connection,
                         result_ttl=result_ttl, status=Status.QUEUED)
        yield self.enqueue_job(job, timeout=timeout)
        defer.returnValue(job)

    @defer.inlineCallbacks
    def enqueue(self, f, *args, **kwargs):
        """Creates a job to represent the delayed function call and enqueues
        it.

        Expects the function to call, along with the arguments and keyword
        arguments.

        The function argument `f` may be any of the following:

        * A reference to a function
        * A reference to an object's instance method
        * A string, representing the location of a function (must be
          meaningful to the import context of the workers)
        """
        if not isinstance(f, basestring) and f.__module__ == '__main__':
            raise ValueError(
                    'Functions from the __main__ module cannot be processed '
                    'by workers.')

        # Detect explicit invocations, i.e. of the form:
        #     q.enqueue(foo, args=(1, 2), kwargs={'a': 1}, timeout=30)
        timeout = None
        result_ttl = None
        if 'args' in kwargs or 'kwargs' in kwargs:
            assert args == (), 'Extra positional arguments cannot be used when using explicit args and kwargs.'  # noqa
            timeout = kwargs.pop('timeout', None)
            args = kwargs.pop('args', None)
            result_ttl = kwargs.pop('result_ttl', None)
            kwargs = kwargs.pop('kwargs', None)

        job = yield self.enqueue_call(func=f, args=args, kwargs=kwargs,
                                 timeout=timeout, result_ttl=result_ttl)
        defer.returnValue(job)

    @defer.inlineCallbacks
    def enqueue_job(self, job, timeout=None, set_meta_data=True):
        """Enqueues a job for delayed execution.

        When the `timeout` argument is sent, it will overrides the default
        timeout value of 180 seconds.  `timeout` may either be a string or
        integer.

        If the `set_meta_data` argument is `True` (default), it will update
        the properties `origin` and `enqueued_at`.

        If Queue is instantiated with async=False, job is executed immediately.
        """
        if set_meta_data:
            job.origin = self.name
            job.enqueued_at = times.now()

        if timeout:
            job.timeout = timeout  # _timeout_in_seconds(timeout)
        else:
            job.timeout = 180  # default
        yield job.save()
        yield self.push_job(job)

    @classmethod
    @defer.inlineCallbacks
    def lpop(cls, queue_keys, timeout, connection=None):
        if connection is None:
            connection = RedisMixin.redis_conn
        if not timeout:  # blocking variant
                raise ValueError('RQ does not support indefinite timeouts. Please pick a timeout value > 0.')
        ret = yield connection.blpop(queue_keys, timeout)
        defer.returnValue(ret)
    
    @defer.inlineCallbacks
    def dequeue(self, timeout):
        '''
        Return first job in queue or None if no job
        '''
        ret = yield self.lpop([self.key], timeout, self.connection)
        if not ret is None:
            _, job_id = ret
            ret = yield Job.fetch(job_id)
        defer.returnValue(ret)
    
    @classmethod
    @defer.inlineCallbacks
    def dequeue_any(cls, queue_keys, timeout, connection=None):
        if connection is None:
            connection = RedisMixin.redis_conn
        
        ret = yield cls.lpop(queue_keys, timeout, connection)
        
        if not ret is None:
            queue_key, job_id = ret
            job = yield Job.fetch(job_id)
            ret = None if job is None else (queue_key, job)
        
        defer.returnValue(ret)

class FailedQueue(Queue):
    def __init__(self, connection=None):
        super(FailedQueue, self).__init__('failed', connection=connection)

    @defer.inlineCallbacks
    def quarantine(self, job, exc_info):
        """Puts the given Job in quarantine (i.e. put it on the failed
        queue).

        This is different from normal job enqueueing, since certain meta data
        must not be overridden (e.g. `origin` or `enqueued_at`) and other meta
        data must be inserted (`ended_at` and `exc_info`).
        """
        job.ended_at = times.now()
        job.exc_info = exc_info
        job.status = Status.FAILED
        ret = yield self.enqueue_job(job, timeout=job.timeout, set_meta_data=False)
        defer.returnValue(ret)

    def requeue(self, job_id):
        """Requeues the job with the given job ID."""
        def handle_error(failure):
            r = failure.trap(NoSuchJobError, UnpickleError)
            return self.remove(r.job_id)
        
        def requeue_job(job):
            job.status = Status.QUEUED
            job.exc_info = None
            q = Queue(job.origin, connection=job.connection)
            return q.enqueue_job(job, timeout=job.timeout)
        
        d = Job.fetch(job_id, connection=self.connection)
        d.addErrback(handle_error)
        d.addCallback(self.remove)
        d.addCallback(requeue_job)
        return d