'''
Created on May 27, 2013

@author: pvicente
'''
from pickle import loads, dumps
from rq.exceptions import NoSuchJobError, UnpickleError
from rq.job import unpickle, Job
from twisted.internet import defer
from cyclone import redis
import times

class RedisMixin(object):
    redis_conn = None

    @classmethod
    def setup(cls):
        # read settings from a conf file or something...
        cls.redis_conn = redis.lazyConnectionPool()

class RQTwistedJob(Job):

    def __init__(self, job_id=None, connection=None):
        self.connection = RedisMixin.redis_conn
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
        connection = RedisMixin.redis_conn
        return connection.exists(cls.key_for(job_id))

    @classmethod
    def fetch(cls, id, connection=None):
        """Fetches a persisted job from its corresponding Redis key and
        instantiates it.
        """
        job = cls(id, connection=connection)
        return job.refresh()

    @classmethod
    def safe_fetch(cls, id, connection=None):
        """Fetches a persisted job from its corresponding Redis key, but does
        not instantiate it, making it impossible to get UnpickleErrors.
        """
        job = cls(id, connection=connection)
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

        return self.connection.hmset(key, obj)

    def delete(self):
        """Deletes the job hash from Redis."""
        return self.connection.delete(self.key)

