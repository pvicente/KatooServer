'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import KatooApp, conf
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.rqtwisted.job import Job
from katoo.rqtwisted.queue import Queue
from katoo.system import DistributedAPI, SynchronousCall, AsynchronousCall
from katoo.xmpp.xmppgoogle import XMPPGoogle
from twisted.internet import defer

class API(DistributedAPI):
    
    def _shared_login(self, xmppuser):
        userid = xmppuser.userid
        running_client = KatooApp().getService(userid)
        if not running_client is None:
            raise XMPPUserAlreadyLogged('Service %s already running'%(running_client))
        XMPPGoogle(xmppuser, KatooApp().app)
    
    @defer.inlineCallbacks
    def _shared_logout(self, userid):
        self.log.info('LOGOUT')
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        user = running_client.user
        yield running_client.disconnect()
        yield user.remove(userid)
    
    @SynchronousCall(queue=conf.DIST_QUEUE_LOGIN)
    @defer.inlineCallbacks
    def login(self, xmppuser):
        self.log.info('LOGIN %s. Data: %s', xmppuser.jid, xmppuser)
        yield self._shared_login(xmppuser)
        xmppuser.worker=conf.MACHINEID
        yield xmppuser.save()
    
    @AsynchronousCall(queue=conf.DIST_QUEUE_RELOGIN)
    @defer.inlineCallbacks
    def relogin(self, xmppuser, pending_jobs):
        self.log.info('RELOGIN %s. Pending_Jobs: %s. Data: %s', xmppuser.jid, len(pending_jobs), xmppuser)
        yield self._shared_login(xmppuser)
        
        xmppuser.onMigration=True
        yield xmppuser.save()
        
        queue = Queue(conf.MACHINEID)
        
        #Enqueue pending jobs before migration was launched
        for job_id in pending_jobs:
            job = yield Job.fetch(job_id, queue.connection)
            yield queue.enqueue_job(job)
        
        #Enqueue pending jobs after migration was launched
        migration_queue = Queue(xmppuser.userid)
        migration_job_ids = yield migration_queue.job_ids
        
        while migration_job_ids:
            job_id = migration_job_ids.pop(0)
            job = yield Job.fetch(job_id, migration_queue.connection)
            
            #Enqueue job in current worker queue
            yield queue.enqueue_job(job)
            
            if not migration_job_ids:
                xmppuser.worker=conf.MACHINEID
                yield xmppuser.save()
                migration_job_ids = yield migration_queue.job_ids
        
        xmppuser.worker=conf.MACHINEID
        xmppuser.onMigration=False
        yield xmppuser.save()
        
    
    @AsynchronousCall(queue=None) #Queue is assigned at run time
    def update(self, userid, **kwargs):
        self.log.info('UPDATE. Data: %s', kwargs)
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        xmppuser = running_client.user
        xmppuser.update(**kwargs)
        return xmppuser.save()
    
    @AsynchronousCall(queue=None) #Queue is assigned at run time
    @defer.inlineCallbacks
    def logout(self, userid):
        yield self._shared_logout(userid)
    
    @AsynchronousCall(queue=None)
    @defer.inlineCallbacks
    def logout_sync(self, userid):
        yield self._shared_logout(userid)
    
    @AsynchronousCall(queue=None) #Queue is assigned at run time
    def disconnect(self, userid, change_state=True):
        self.log.info('DISCONNECTING')
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        return running_client.disconnect(change_state)
    