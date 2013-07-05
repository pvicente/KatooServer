'''
Created on Jun 2, 2013

@author: pvicente
'''
from katoo.utils.connections import RedisMixin
from pickle import loads, dumps
from rq.exceptions import NoSuchJobError, UnpickleError
from rq.job import unpickle
from twisted.internet import defer
import importlib
import rq
import times

class Job(rq.job.Job):
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
    @defer.inlineCallbacks
    def fetch(cls, job_id, connection=None):
        """Fetches a persisted job from its corresponding Redis key and
        instantiates it.
        """
        if job_id is None:
            yield defer.returnValue(None)
        job = cls(job_id, connection=connection)
        yield job.refresh()
        defer.returnValue(job)

    @classmethod
    @defer.inlineCallbacks
    def safe_fetch(cls, job_id, connection=None):
        """Fetches a persisted job from its corresponding Redis key, but does
        not instantiate it, making it impossible to get UnpickleErrors.
        """
        if job_id is None:
            yield defer.returnValue(None)
        job = cls(job_id, connection=connection)
        yield job.refresh()
        defer.returnValue(job)
    
    @defer.inlineCallbacks
    def _get_status(self):
        self._status = yield self.connection.hget(self.key, 'status')
        defer.returnValue(self._status)
    
    def _set_status(self, status):
        self._status = status

    status = property(_get_status, _set_status)

    @defer.inlineCallbacks
    def _get_result(self):
        if self._result is None:
            rv = yield self.connection.hget(self.key, 'result')
            if rv is not None:
                self._result = loads(str(rv))
        defer.returnValue(self._result)
    
    result = property(_get_result)
    
    """Backwards-compatibility accessor property `return_value`."""
    return_value = result
    
    @defer.inlineCallbacks
    def refresh(self):
        """Overwrite the current instance's properties with the values in the
        corresponding Redis key.

        Will raise a NoSuchJobError if no corresponding Redis key exists.
        """
        obj = yield self.connection.hgetall(self.key)
        if len(obj) == 0:
            e = NoSuchJobError('No such job: %s' % (self.key,))
            e.job_id = self.id
            raise e
        
        def to_date(date_str):
            if date_str is None:
                return None
            else:
                return times.to_universal(date_str)
        
        try:
            self.data = str(obj['data'])
        except KeyError:
            e = NoSuchJobError('Unexpected job format: {0}'.format(obj))
            e.job_id = self.id
            raise e
        
        try:
            self._func_name, self._instance, self._args, self._kwargs = unpickle(self.data)
        except UnpickleError as e:
            e.job_id = self.id
            raise e
        
        self.created_at = to_date(obj.get('created_at'))
        self.origin = obj.get('origin')
        self.description = obj.get('description')
        self.enqueued_at = to_date(obj.get('enqueued_at'))
        self.ended_at = to_date(obj.get('ended_at'))
        self._result = unpickle(str(obj.get('result'))) if obj.get('result') else None  # noqa
        self.exc_info = unpickle(str(obj.get('exc_info'))) if obj.get('exc_info') else None  # noqa
        self.timeout = int(obj.get('timeout')) if obj.get('timeout') else None
        self.result_ttl = int(obj.get('result_ttl')) if obj.get('result_ttl') else None # noqa
        self._status = obj.get('status') if obj.get('status') else None
        self.meta = unpickle(obj.get('meta')) if obj.get('meta') else {}
    
    @defer.inlineCallbacks
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
        
        yield self.connection.hmset(key, obj)
        
    def delete(self):
        """Deletes the job hash from Redis."""
        return self.connection.delete(self.key)
    
    def perform(self):
        """Invokes the job function with the job arguments."""
        self._result = self.func(*self.args, **self.kwargs)
        return self._result, self
    
    @property
    def func(self):
        func_name = self.func_name
        if func_name is None:
            return None
        
        if self.instance:
            try:
                return getattr(self.instance, func_name)
            except:
                raise UnpickleError('function "%s" not found in object "%s". Cannot be performed'%(func_name, self.instance), raw_data=self.data)
        
        module_name, func_name = func_name.rsplit('.', 1)
        module = importlib.import_module(module_name)
        try:
            return getattr(module, func_name)
        except:
            raise UnpickleError('function "%s" not found in module "%s". Cannot be performed'%(func_name, module_name), raw_data=self.data)

