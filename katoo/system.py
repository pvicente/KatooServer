'''
Created on Jul 2, 2013

@author: pvicente
'''
from functools import wraps
from katoo import conf
from katoo.exceptions import XMPPUserNotLogged, DistributedJobTimeout, \
    DistributedJobFailure
from katoo.rqtwisted.job import Job
from katoo.rqtwisted.queue import Queue, Status
from katoo.utils.applog import getLogger, getLoggerAdapter
from katoo.utils.time import sleep
from twisted.internet import defer

log = getLogger(__name__)

class DistributedAPI(object):
    """API with distributed behaviour must subclass it to be performed"""
    def __init__(self, key=None, queue=None, synchronous_call=False):
        self.key = key
        self.queue_name = None if conf.DIST_DISABLED else queue
        self.enqueued = False
        self.sync = synchronous_call
        self._log = getLoggerAdapter(log, id=self.key)

    
    def __getstate__(self):
        self._log = None
        return self.__dict__
    
    @property
    def log(self):
        if self._log is None:
            self._log = getLoggerAdapter(log, id=self.key)
        return self._log
    
class SynchronousCall(object):
    """Make a synchronous call enqueing job in queue and returning result"""
    def __init__(self, queue):
        self.queue_name=None if conf.DIST_DISABLED else queue
        self.sync = True
        self.result_ttl = conf.DIST_DEFAULT_TTL
    
    @defer.inlineCallbacks
    def get_result(self, job):
        #TODO: Improve pulling using reactor.callLater (https://twistedmatrix.com/documents/12.0.0/core/howto/time.html) if possible now we are using reactor.callLater in sleep
        yield sleep(conf.DIST_FIRST_PULL_TIME)
        status = yield job.status
        total_time = conf.DIST_FIRST_PULL_TIME
        while status == Status.QUEUED:
            yield sleep(conf.DIST_PULL_TIME)
            
            total_time += conf.DIST_PULL_TIME
            if total_time >= conf.DIST_TIMEOUT_TIME:
                job_description = str(job)
                #TODO: pending to remove from queue (if not a controlled exception will be launched in worker)
                yield job.delete()
                raise DistributedJobTimeout('Timeout %s performing distributed job %s'%(total_time, job_description))
            
            #print 'Pulling time:', total_time
            status = yield job.status
        
        ret = None
        if status == Status.FINISHED:
            ret = yield job.result
        elif status == Status.FAILED:
            yield job.refresh()
            failure = job.meta.get('failure')
            if failure is None:
                raise DistributedJobFailure('Job %s failed without traceback', job)
            failure.raiseException()
        defer.returnValue(ret)
    
    def __call__(self, f):
        @wraps(f)
        @defer.inlineCallbacks
        def wrapped_f(*args, **kwargs):
            if len(args) == 0 or not isinstance(args[0], DistributedAPI):
                raise TypeError('SynchronousCall must be called with a DistributedAPI object')
            calling_self = args[0]
            args = args[1:]
            
            #More precedence queue_name of DistributedAPI than decorated method
            queue_name = calling_self.queue_name if calling_self.queue_name else self.queue_name
            
            ret = None
            if calling_self.enqueued or not queue_name:
                ret = yield f(calling_self, *args, **kwargs)
            else:
                function = getattr(calling_self, getattr(f, 'func_name'))
                queue = Queue(queue_name)
                calling_self.enqueued = True
                job = Job.create(func=function, args=args, kwargs=kwargs, connection=queue.connection,
                         result_ttl=self.result_ttl, status=Status.QUEUED)
                job.meta['userid']=calling_self.key
                yield queue.enqueue_job(job)
                if self.sync or calling_self.sync:
                    ret = yield self.get_result(job)
            defer.returnValue(ret)
        return wrapped_f

class AsynchronousCall(SynchronousCall):
    def __init__(self, queue):
        SynchronousCall.__init__(self, queue)
        self.sync = conf.DIST_ASYNC_AS_SYNC
        self.result_ttl = conf.DIST_DEFAULT_TTL if conf.DIST_ASYNC_AS_SYNC else 0

if __name__ == '__main__':
    from katoo import KatooApp
    from katoo.api import API
    from twisted.internet import reactor
    from katoo.rqtwisted.worker import Worker
    from katoo.data import GoogleUser
    from pickle import dumps
    
    my_log = getLoggerAdapter(getLogger(__name__))
    @defer.inlineCallbacks
    def example():
        job = Job(job_id="123")
        pickled_rv = dumps({'results': None})
        yield job.save()
        yield job.connection.hset(job.key, 'result', pickled_rv)
        res = yield job.result
        my_log.debug('Job result %s', res)
        
        user=GoogleUser(_userid="1", _token="asdasdf", _refreshtoken="refreshtoken", _resource="unknownresource", _pushtoken="", _badgenumber="0", _pushsound="asdfasdfas", _jid='kk@gmail.com')
        my_log.info('User:%s before saving'%(user))
        res = yield user.save()
        my_log.info('User %s: saved. Res %s'%(user, res))
        ret = yield API(user.userid).login(user)
        my_log.info('Login result %s. Sleeping 10 seconds', ret)
        yield sleep(5)
        my_log.info('Result login %s', ret)
        try:
            ret = yield API(user.userid, conf.MACHINEID).logout(user.userid)
        except XMPPUserNotLogged as e:
            my_log.error('Exception launch %s', e)
        try:
            ret = yield API(user.userid).logout(user.userid)
        except XMPPUserNotLogged as e:
            my_log.error('Exception launch %s', e)
        
        #Perform a timeout
        ret = yield API(user.userid, 'default').login(user)
        
#        reactor.callLater(5, API(user.userid).login, user)
#        reactor.callLater(7, API(user.userid).update, user.userid, token="ya29.AHES6ZRDTu4pDWdA_LBrNWF1vnI5NEtdB8V0v6JN46QTaw")
#        reactor.callLater(10, API(user.userid).logout, user.userid)
#        reactor.callLater(20, API(user.userid).login, user)
    
    #log.startLogging(sys.stdout)
    
    app = KatooApp().app
    w=Worker([conf.MACHINEID, conf.DIST_QUEUE_LOGIN], name=conf.MACHINEID, loops=conf.REDIS_WORKERS)
    w.log = getLoggerAdapter(getLogger('WORKER', level='INFO'), id='WORKER-%s'%(conf.MACHINEID))
    w.setServiceParent(app)
    KatooApp().service.startService()
    reactor.callLater(5, example)
    import twisted.python.log
    twisted.python.log.startLoggingWithObserver(KatooApp().log.emit)
    reactor.callLater(50, reactor.stop)
    reactor.run()
