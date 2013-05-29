'''
Created on May 27, 2013

@author: pvicente
'''
from cyclone import redis
from functools import total_ordering
from katoo.utils.parse import redis_url_parse
from pickle import loads, dumps
from rq.exceptions import NoSuchJobError, UnpickleError
from rq.job import unpickle, Job, Status
from rq.queue import Queue, compact
from twisted.internet import defer
import times
from katoo import conf

class RedisMixin(object):
    redis_conn = None

    @classmethod
    def setup(cls):
        hostname, port, db, password = redis_url_parse(conf.REDIS_URL)
        #pending to resolve Authentication with redis in cyclone.redis library
        cls.redis_conn = redis.lazyConnectionPool(host=hostname, port=port, dbid=db, poolsize=conf.REDIS_POOL)

class RQTwistedJob(Job):

    def __init__(self, job_id=None, connection=None):
        if connection is None:
            connection = RedisMixin.redis_conn
        self.connection = connection
        self._id = job_id
        self.created_at = times.now()
        self._func_name = None
        self._instance = None
        self._args = None
        self._kwargs = None
        self.description = None
        self.origin = None
        self.enqueued_at = None
        self.ended_at = None
        self._result = None
        self.exc_info = None
        self.timeout = None
        self.result_ttl = None
        self._status = None
        self.meta = {}

    @classmethod
    def exists(cls, job_id, connection=None):
        """Returns whether a job hash exists for the given job ID."""
        if connection is None:
            connection = RedisMixin.redis_conn
        return connection.exists(cls.key_for(job_id))

    @classmethod
    def fetch(cls, job_id, connection=None):
        """Fetches a persisted job from its corresponding Redis key and
        instantiates it.
        """
        if job_id is None:
            return defer.succeed(None)
        job = cls(job_id, connection=connection)
        return job.refresh()

    @classmethod
    def safe_fetch(cls, job_id, connection=None):
        """Fetches a persisted job from its corresponding Redis key, but does
        not instantiate it, making it impossible to get UnpickleErrors.
        """
        if job_id is None:
            return defer.succeed(None)
        job = cls(job_id, connection=connection)
        return job.refresh()

    def _get_status_impl(self, value):
        self._status = value
        return defer.succeed(self._status)
    
    def _get_status(self):
        d = self.connection.hget(self.key, 'status')
        d.addCallback(self._get_status_impl)
        return d
        
    def _set_status(self, status):
        self._status = status
        return self.connection.hset(self.key, 'status', self._status)

    status = property(_get_status, _set_status)

    def _result_impl(self, value):
        if value is not None:
                # cache the result
                self._result = loads(value)
        return defer.succeed(self._result)  

    @property
    def result(self):
        """Returns the return value of the job.

        Initially, right after enqueueing a job, the return value will be
        None.  But when the job has been executed, and had a return value or
        exception, this will return that value or exception.

        Note that, when the job has no return value (i.e. returns None), the
        ReadOnlyJob object is useless, as the result won't be written back to
        Redis.

        Also note that you cannot draw the conclusion that a job has _not_
        been executed when its return value is None, since return values
        written back to Redis will expire after a given amount of time (500
        seconds by default).
        """
        if self._result is None:
            d = self.connection.hget(self.key, 'result')
            d.addCallback(self._result_impl)
            return d
        return defer.succeed(self._result)

    """Backwards-compatibility accessor property `return_value`."""
    return_value = result
    
    def refresh_impl(self, obj):
        if len(obj) == 0:
            raise NoSuchJobError('No such job: %s' % (self.key,))

        def to_date(date_str):
            if date_str is None:
                return None
            else:
                return times.to_universal(date_str)

        try:
            self.data = str(obj['data'])
        except KeyError:
            raise NoSuchJobError('Unexpected job format: {0}'.format(obj))

        try:
            self._func_name, self._instance, self._args, self._kwargs = unpickle(self.data)
        except UnpickleError:
                raise
        self.created_at = to_date(obj.get('created_at'))
        self.origin = obj.get('origin')
        self.description = obj.get('description')
        self.enqueued_at = to_date(obj.get('enqueued_at'))
        self.ended_at = to_date(obj.get('ended_at'))
        self._result = unpickle(obj.get('result')) if obj.get('result') else None  # noqa
        self.exc_info = obj.get('exc_info')
        self.timeout = int(obj.get('timeout')) if obj.get('timeout') else None
        self.result_ttl = int(obj.get('result_ttl')) if obj.get('result_ttl') else None # noqa
        self._status = obj.get('status') if obj.get('status') else None
        self.meta = unpickle(obj.get('meta')) if obj.get('meta') else {}
        return defer.succeed(self)
    
    
    def refresh(self):
        """Overwrite the current instance's properties with the values in the
        corresponding Redis key.

        Will raise a NoSuchJobError if no corresponding Redis key exists.
        """
        d = self.connection.hgetall(self.key)
        d.addCallback(self.refresh_impl)
        return d
    
    def save(self):
        """Persists the current job instance to its corresponding Redis key."""
        key = self.key

        obj = {}
        obj['created_at'] = times.format(self.created_at or times.now(), 'UTC')

        if self.func_name is not None:
            obj['data'] = dumps(self.job_tuple)
        if self.origin is not None:
            obj['origin'] = self.origin
        if self.description is not None:
            obj['description'] = self.description
        if self.enqueued_at is not None:
            obj['enqueued_at'] = times.format(self.enqueued_at, 'UTC')
        if self.ended_at is not None:
            obj['ended_at'] = times.format(self.ended_at, 'UTC')
        if self._result is not None:
            obj['result'] = dumps(self._result)
        if self.exc_info is not None:
            obj['exc_info'] = self.exc_info
        if self.timeout is not None:
            obj['timeout'] = self.timeout
        if self.result_ttl is not None:
            obj['result_ttl'] = self.result_ttl
        if self._status is not None:
            obj['status'] = self._status
        if self.meta:
            obj['meta'] = dumps(self.meta)

        d = self.connection.hmset(key, obj)
        d.addCallback(lambda x: self.id)
        return d

    def delete(self):
        """Deletes the job hash from Redis."""
        return self.connection.delete(self.key)

@total_ordering
class RQTwistedQueue(Queue):

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
        job_id = job_or_id.id if isinstance(job_or_id, RQTwistedJob) else job_or_id
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
            if RQTwistedJob.exists(job_id):
                yield self.connection.rpush(self.key, job_id)
    
    
    def push_job_id(self, job_or_id):  # noqa
        """Pushes a job ID on the corresponding Redis queue."""
        job_id = job_or_id.id if isinstance(job_or_id, RQTwistedJob) else job_or_id
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
        job = RQTwistedJob.create(func, args, kwargs, connection=self.connection,
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
        d.addCallback(RQTwistedJob.fetch)
        return d

    @classmethod
    def dequeue_any(cls, queue_keys, timeout, connection=None):
        def get_queue_job(res):
            if res is None:
                return defer.succeed(None)
            queue_key, job_id = res
            queue = cls.from_queue_key(queue_key)
            d = RQTwistedJob.fetch(job_id, connection)
            d.addCallback(lambda job: job if job is None else (queue, job))
            return d
            
        if connection is None:
            connection = RedisMixin.redis_conn
        d = cls.lpop(queue_keys, timeout, connection)
        d.addCallback(get_queue_job)
        return d
        
