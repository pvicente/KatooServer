'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import KatooApp, conf
from katoo.data import GoogleUser
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.metrics import Metric
from katoo.rqtwisted.job import Job, NoSuchJobError
from katoo.rqtwisted.queue import Queue
from katoo.system import DistributedAPI, SynchronousCall, AsynchronousCall
from katoo.utils.time import Timer
from katoo.xmpp.xmppgoogle import XMPPGoogle
from twisted.internet import defer

METRIC_INCREMENT = 1 if conf.REDIS_WORKERS == 0 else 0.5
METRIC_UNIT = 'calls'
METRIC_SOURCE = 'KATOO_API'

class API(DistributedAPI):
    
    def _shared_login(self, xmppuser):
        userid = xmppuser.userid
        running_client = KatooApp().getService(userid)
        if not running_client is None:
            raise XMPPUserAlreadyLogged('Service %s already running'%(running_client))
        XMPPGoogle(xmppuser, KatooApp().app)
    
    @Metric(name='login', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @SynchronousCall(queue=conf.DIST_QUEUE_LOGIN)
    @defer.inlineCallbacks
    def login(self, xmppuser):
        self.log.info('LOGIN %s. Data: %s', xmppuser.jid, xmppuser)
        yield self._shared_login(xmppuser)
        xmppuser.worker=conf.MACHINEID
        yield xmppuser.save()
    
    @Metric(name='relogin', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @AsynchronousCall(queue=conf.DIST_QUEUE_RELOGIN)
    @defer.inlineCallbacks
    def relogin(self, xmppuser, pending_jobs):
        len_pending_jobs = len(pending_jobs)
        self.log.info('RELOGIN %s. Pending_Jobs: %s. Data: %s', xmppuser.jid, len_pending_jobs, xmppuser)
        yield self._shared_login(xmppuser)
        
        xmppuser.onMigrationTime = Timer().utcnow()
        yield xmppuser.save()
        
        queue = Queue(conf.MACHINEID)
        
        self.log.info('perform relogin %s. Enqueuing pending jobs %s before migration was launched. Data %s', xmppuser.jid, len_pending_jobs, xmppuser)
        #Enqueue pending jobs before migration was launched
        for job_id in pending_jobs:
            try:
                job = yield Job.fetch(job_id, queue.connection)
                yield queue.enqueue_job(job)
            except NoSuchJobError:
                pass
        self.log.info('perform relogin %s. Finished enqueuing pending jobs before migration was launched.', xmppuser.jid)
        
        self.log.info('perform relogin %s. Enqueing pending jobs after migration was launched.', xmppuser.jid)
        #Enqueue pending jobs after migration was launched
        migration_queue = Queue(xmppuser.userid)
        migration_job_ids = yield migration_queue.job_ids
        yield migration_queue.empty()
        
        while migration_job_ids:
            job_id = migration_job_ids.pop(0)
            try:
                job = yield Job.fetch(job_id, migration_queue.connection)
                #Enqueue job in current worker queue
                yield queue.enqueue_job(job)
            except NoSuchJobError:
                pass
            
            if not migration_job_ids:
                xmppuser.worker=conf.MACHINEID
                xmppuser.onMigrationTime=''
                yield xmppuser.save()
                migration_job_ids = yield migration_queue.job_ids
                yield migration_queue.empty()
        
        self.log.info('perform relogin %s. Finished enqueing jobs after migration was launched. Data %s', xmppuser.jid, xmppuser)
        
        if xmppuser.worker != conf.MACHINEID:
            xmppuser.worker=conf.MACHINEID
            xmppuser.onMigrationTime=''
            yield xmppuser.save()
        
        self.log.info('RELOGIN %s. Finished. Data %s', xmppuser.jid, xmppuser)
    
    @Metric(name='update', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @AsynchronousCall(queue=None) #Queue is assigned at runtime
    def update(self, userid, **kwargs):
        self.log.info('UPDATE. Data: %s', kwargs)
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        xmppuser = running_client.user
        xmppuser.update(**kwargs)
        return xmppuser.save()
    
    @Metric(name='update_contact', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @AsynchronousCall(queue=None) #Queue is assigned at run time
    @defer.inlineCallbacks
    def update_contact(self, userid, jid, **kwargs):
        self.log.info('UPDATE CONTACT %s. Data: %s', jid, kwargs)
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        roster = running_client.roster
        yield roster.set(jid, **kwargs)
    
    @Metric(name='update_presence', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @AsynchronousCall(queue=None) #Queue is assigned at run time
    @defer.inlineCallbacks
    def update_presence(self, userid, jid, **kwargs):
        self.log.info('UPDATE PRESENCE %s. Data: %s', jid, kwargs)
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        roster = running_client.roster
        yield roster.set(jid, **kwargs)
    
    @Metric(name='logout', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @AsynchronousCall(queue=None) #Queue is assigned at runtime
    @defer.inlineCallbacks
    def logout(self, userid):
        try:
            self.log.info('LOGOUT')
            running_client = KatooApp().getService(userid)
            if running_client is None:
                raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
            yield running_client.disconnect()
        except XMPPUserNotLogged:
            pass
        finally:
            yield GoogleUser.remove(userid)
    
    @Metric(name='disconnect', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @AsynchronousCall(queue=None) #Queue is assigned at runtime
    def disconnect(self, userid, change_state=True):
        self.log.info('DISCONNECTING')
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        return running_client.disconnect(change_state)
    