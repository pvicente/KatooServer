'''
Created on Jul 2, 2013

@author: pvicente
'''
from functools import wraps
from katoo.rqtwisted.job import Job
from katoo.rqtwisted.queue import Queue, Status
from twisted.internet import defer, reactor
from katoo.exceptions import XMPPUserNotLogged

def sleep(secs):
    d = defer.Deferred()
    reactor.callLater(secs, d.callback, None)
    return d

@defer.inlineCallbacks
def get_result(job_id):
    job = yield Job.fetch(job_id)
    status = yield job.status
    while status == Status.QUEUED:
        yield sleep(0.5)
        status = yield job.status
    
    ret = None
    if status == Status.FINISHED:
        ret = yield job.result
    elif status == Status.FAILED:
        job = yield job.fetch(job_id, job.connection)
        failure = job.exc_info
        if not failure is None:
            failure.raiseException()
    defer.returnValue(ret)

def synchronous_action(f):
    @wraps(f)
    @defer.inlineCallbacks
    def wrapper(self, *args, **kwargs):
        if self.enqueued or self.queue_name is None:
            ret = yield f(self, *args, **kwargs)
        else:
            function = getattr(self, getattr(f, 'func_name'))
            queue = Queue(self.queue_name)
            self.enqueued = True
            ret = yield queue.enqueue_call(func=function, args=args, kwargs=kwargs)
            ret = yield get_result(ret)
        defer.returnValue(ret)
    return wrapper

if __name__ == '__main__':
    from katoo import KatooApp, conf
    from katoo.api import API
    from katoo.utils.applog import getLoggerAdapter, getLogger
    from twisted.internet import reactor
    from katoo.rqtwisted.worker import Worker
    from katoo.data import GoogleUser
    from katoo.rqtwisted.job import Job
    from pickle import dumps
    
    my_log = getLoggerAdapter(getLogger(__name__))
    @defer.inlineCallbacks
    def example():
        job = Job(job_id="123")
        pickled_rv = dumps({'results': None})
        yield job.save()
        yield job.connection.hset(job.key, 'result', pickled_rv)
        res= yield job.result
        
        user=GoogleUser(_userid="1", _token="asdasdf", _refreshtoken="refreshtoken", _resource="unknownresource", _pushtoken="", _badgenumber="0", _pushsound="asdfasdfas", _jid='kk@gmail.com')
        my_log.info('User:%s before saving'%(user))
        res = yield user.save()
        my_log.info('User %s: saved. Res %s'%(user, res))
        ret = yield API(user.userid, 'default').login(user)
        my_log.info('Login result %s. Sleeping 10 seconds', ret)
        yield sleep(10)
        my_log.info('Result login %s', ret)
        try:
            ret = yield API(user.userid, 'default').logout(user.userid)
        except XMPPUserNotLogged as e:
            my_log.error('Exception launch %s', e)
        try:
            ret = yield API(user.userid).logout(user.userid)
        except XMPPUserNotLogged as e:
            my_log.error('Exception launch %s', e)
        
#        reactor.callLater(5, API(user.userid).login, user)
#        reactor.callLater(7, API(user.userid).update, user.userid, token="ya29.AHES6ZRDTu4pDWdA_LBrNWF1vnI5NEtdB8V0v6JN46QTaw")
#        reactor.callLater(10, API(user.userid).logout, user.userid)
#        reactor.callLater(20, API(user.userid).login, user)
    
    #log.startLogging(sys.stdout)
    
    app = KatooApp().app
    w=Worker(['default'], name=conf.MACHINEID, loops=conf.REDIS_WORKERS)
    w.log = getLoggerAdapter(getLogger('WORKER', level='INFO'), id='WORKER-%s'%(conf.MACHINEID))
    w.setServiceParent(app)
    KatooApp().service.startService()
    reactor.callLater(5, example)
    import twisted.python.log
    twisted.python.log.startLoggingWithObserver(KatooApp().log.emit)
    reactor.callLater(50, reactor.stop)
    reactor.run()
