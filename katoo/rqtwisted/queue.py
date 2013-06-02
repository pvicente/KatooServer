'''
Created on Jun 2, 2013

@author: pvicente
'''
from functools import total_ordering
from katoo.rqtwisted.job import Job
from katoo.utils.redis import RedisMixin
from rq.exceptions import NoSuchJobError, UnpickleError
from rq.job import Status
from rq.queue import compact
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
        raise NotImplemented()
        """Returns a list of all (valid) jobs in the queue."""
        def safe_fetch(job_id):
            try:
                job = yield Job.safe_fetch(job_id)
            except NoSuchJobError:
                yield self.remove(job_id)
            except UnpickleError:
                yield
            yield job
        
        return compact([safe_fetch(job_id) for job_id in self.job_ids])

    def remove(self, job_or_id):
        """Removes Job from queue, accepts either a Job instance or ID."""
        job_id = job_or_id.id if isinstance(job_or_id, Job) else job_or_id
        return self.connection.lrem(self.key, 0, job_id)
    
    def compact(self):
        raise NotImplemented()
        """Removes all "dead" jobs from the queue by cycling through it, while
        guarantueeing FIFO semantics.
        """
        COMPACT_QUEUE = 'rq:queue:_compact'

        yield self.connection.rename(self.key, COMPACT_QUEUE)
        while True:
            job_id = yield self.connection.lpop(COMPACT_QUEUE)
            if job_id is None:
                break
            if Job.exists(job_id):
                yield self.connection.rpush(self.key, job_id)
    
    
    def push_job_id(self, job_or_id):  # noqa
        """Pushes a job ID on the corresponding Redis queue."""
        job_id = job_or_id.id if isinstance(job_or_id, Job) else job_or_id
        d = self.connection.rpush(self.key, job_id)
        d.addCallback(lambda x: job_id)
        return d

    
    def pop_job_id(self):
        """Pops a given job ID from this Redis queue."""
        return self.connection.lpop(self.key)
    

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
        return self.enqueue_job(job, timeout=timeout)

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

        return self.enqueue_call(func=f, args=args, kwargs=kwargs,
                                 timeout=timeout, result_ttl=result_ttl)

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
        d = job.save()
        d.addCallback(self.push_job_id)
        return d

    @classmethod
    def lpop(cls, queue_keys, timeout, connection=None):
        if connection is None:
            connection = RedisMixin.redis_conn
        if not timeout:  # blocking variant
                raise ValueError('RQ does not support indefinite timeouts. Please pick a timeout value > 0.')
        d = connection.blpop(queue_keys, timeout)
        #return queue_key, job_id or None
        d.addCallback(lambda x: x if x is None else (x[0], x[1]))
        return d

    def dequeue(self, timeout):
        '''
        Return first job in queue or None if no job
        '''
        d = self.lpop([self.key], timeout, self.connection)
        d.addCallback(lambda x: x if x is None else x[1])
        d.addCallback(Job.fetch)
        return d

    @classmethod
    def dequeue_any(cls, queue_keys, timeout, connection=None):
        def get_queue_job(res):
            if res is None:
                return defer.succeed(None)
            queue_key, job_id = res
            queue = cls.from_queue_key(queue_key)
            d = Job.fetch(job_id, connection)
            d.addCallback(lambda job: job if job is None else (queue, job))
            return d
            
        if connection is None:
            connection = RedisMixin.redis_conn
        d = cls.lpop(queue_keys, timeout, connection)
        d.addCallback(get_queue_job)
        return d
        