'''
Created on Jun 12, 2013

@author: pvicente
'''
from datetime import datetime
from dateutil import parser
from rq.exceptions import NoSuchJobError
from katoo import conf, KatooApp
from katoo.api import API
from katoo.apns.api import API as APNSAPI
from katoo.data import GoogleUser
from katoo.globalmetrics import RedisMetrics, MongoMetrics
from katoo.metrics import MetricsHub, Metric
from katoo.rqtwisted.job import Job
from katoo.rqtwisted.queue import Queue
from katoo.rqtwisted.worker import Worker
from katoo.utils.applog import getLogger, getLoggerAdapter
from katoo.utils.patterns import Subject
from twisted.application import service
from twisted.internet import defer, reactor
from twisted.internet.task import LoopingCall
import cyclone.httpclient
import translate

log = getLogger(__name__, level='INFO')

class Supervisor(service.Service):
    def __init__(self):
        self.tasks = []
    
    def registerTask(self, t):
        self.tasks.append(t)
    
    def stopService(self):
        if self.running:
            service.Service.stopService(self)
            for task in self.tasks:
                self.log.info('STOPPING_TASK %s', task)
                task.stop()

class HerokuUnidlingSupervisor(Supervisor):
    name='HEROKU_UNIDLING_SUPERVISOR'
    log = getLoggerAdapter(log, id=name)
    
    @defer.inlineCallbacks
    def avoidHerokuUnidling(self, url):
        try:
            self.log.info('AVOIDING HEROKU IDLING: %s', url)
            yield cyclone.httpclient.fetch(url)
        except Exception as e:
            self.log.err(e, 'Exception in avoidHerokuUnidling')
    
    def startService(self):
        Supervisor.startService(self)
        if not conf.HEROKU_UNIDLING_URL is None:
            t = LoopingCall(self.avoidHerokuUnidling, conf.HEROKU_UNIDLING_URL)
            self.registerTask(t)
            t.start(1800, now = True)

class MetricsSupervisor(Supervisor, Subject):
    name='METRICS_SUPERVISOR'
    log = getLoggerAdapter(log, id=name)
    
    def __init__(self):
        Supervisor.__init__(self)
        Subject.__init__(self)

    def report(self):
        self.notifyObservers()
        MetricsHub().report()
    
    def startService(self):
        Supervisor.startService(self)
        t = LoopingCall(self.report)
        self.registerTask(t)
        t.start(conf.METRICS_REPORT_TIME, now=False)
    
    def stopService(self):
        Supervisor.stopService(self)

class XMPPKeepAliveSupervisor(Supervisor, Subject):
    name='XMPP_KEEPALIVE_SUPERVISOR'
    log = getLoggerAdapter(log, id=name)
    
    def __init__(self):
        Supervisor.__init__(self)
        Subject.__init__(self)
        self.lastTime = datetime.utcnow()
        self.metric = Metric(name='elapsed_time', value=None, unit='msec', source=self.name, scale=1000, sampling=True)

    def perform_keep_alive(self):
        self.lastTime = datetime.utcnow()
        self.notifyObservers()
        elapsedTime = datetime.utcnow()-self.lastTime
        usecs = elapsedTime.seconds*1000000 + elapsedTime.microseconds
        self.log.info('Finished XMPP_KEEP_ALIVE. Elapsed %s usecs', usecs)
        self.metric.add(usecs)
    
    def startService(self):
        Supervisor.startService(self)
        if conf.XMPP_KEEP_ALIVE_TIME>0:
            t = LoopingCall(self.perform_keep_alive)
            self.registerTask(t)
            t.start(conf.XMPP_KEEP_ALIVE_TIME, now=False)

class GlobalSupervisor(Supervisor):
    name = 'GLOBAL_SUPERVISOR'
    log = getLoggerAdapter(log, id=name)
    DISCONNECT_AWAY_METRIC = Metric(name='away_user_disconnected', value=None, unit='events', source='XMPPGOOGLE')
    
    def __init__(self):
        Supervisor.__init__(self)
        self.lock = defer.DeferredLock()
        self._checkworkerstasks=[self.processDeathWorkers, self.processBadAssignedWorkers, self.processOnMigrationUsers, self.checkRunningWorkers]
        self._globalmetrics=[RedisMetrics, MongoMetrics]
    
    def _attach_global_metrics(self):
        service = KatooApp().getService(MetricsSupervisor.name)
        for metric in self._globalmetrics:
            service.registerObserver(metric())
    
    @defer.inlineCallbacks
    def checkRunningWorkers(self):
        workers = yield Worker.getWorkers(Worker.redis_workers_keys)
        if workers:
            self.log.info('CHECKING_RUNNING_WORKERS %s', len(workers))
        for worker in workers:
            name = worker.get('name')
            key = worker.get('key')
            lastTime = worker.get('lastTime')
            if key is None or name is None or lastTime is None:
                self.log.warning('WORKER_DATA_WRONG %s', worker)
                continue
            death = worker.get('death')
            if death is None:
                lastTime = parser.parse(lastTime)
                delta = datetime.utcnow() - lastTime
                if delta.seconds > conf.SUPERVISOR_WORKER_REFRESH_TIME:
                    self.log.warning('REGISTERING_WORKER_DEATH %s has not been updated since %s second(s)', name, delta.seconds)
                    w = Worker([], name=name)
                    w.log = self.log
                    yield w.register_death()
    
    @defer.inlineCallbacks
    def processOnMigrationUsers(self):
        onMigration_users = yield GoogleUser.get_onMigration()
        total_users = len(onMigration_users)
        if total_users > 0:
            self.log.info("ON_MIGRATION_USERS %s", total_users)
        now = datetime.utcnow()
        for data in onMigration_users:
            user = GoogleUser(**data)
            delta_time = now - user.onMigrationTime
            if delta_time.seconds < 60:
                continue
            self.log.warning('[%s] USER_MIGRATION_STOPPED %s second(s) ago. Performing new relogin. User state: %s', user.userid, delta_time.seconds, user)
            user.worker = user.userid
            user.onMigrationTime=''
            yield user.save()
            yield API(user.userid).relogin(user, pending_jobs=[])
    
    @defer.inlineCallbacks
    def getPendingJobs(self, userid, queue_name):
        queue = Queue(queue_name)
        job_ids = yield queue.job_ids
        jobs = []
        index = 0
        for job_id in job_ids:
            try:
                job = yield Job.fetch(job_id, connection=queue.connection)
                if job.meta.get('userid') == userid:
                    jobs.append(job_id)
            except Exception as e:
                self.log.err(e, '[%s] Exception fetching job %s with index %s while getPendingJobs in queue %s'%(userid, job_id, index, queue_name))
                yield queue.remove(job_id)
            finally:
                index+=1
        defer.returnValue(jobs)
    
    @defer.inlineCallbacks
    def processDeathWorkers(self):
        #avoid process death workers when service is not running
        death_workers = yield Worker.getWorkers(Worker.redis_death_workers_keys) if self.running else []
        
        if death_workers:
            self.log.info('DEATH_WORKERS %s', [worker.get('name') for worker in death_workers])
        for worker in death_workers:
            name = worker.get('name')
            key = worker.get('key')
            if conf.DIST_QUEUE_LOGIN in worker.get('queues', []):
                connected_users = yield GoogleUser.get_connected(name)
                total_users = len(connected_users)
                self.log.info('Reconnecting %s connected user(s) of death worker %s', total_users, name)
                for i in xrange(total_users):
                    try:
                        data = connected_users[i]
                        user = GoogleUser(**data)
                        
                        #Update worker as userid to enqueue new jobs in user own queue
                        user.worker=user.userid
                        yield user.save()
                        
                        #Get pending jobs
                        pending_jobs = yield self.getPendingJobs(user.userid, name)
                        yield API(user.userid).relogin(user, pending_jobs)
                        self.log.info('[%s] Reconnected %s/%s user(s) of worker %s', user.userid, i+1, total_users, name)
                    except Exception as e:
                        self.log.err(e, '[%s] Exception while reconnecting'%(data['_userid']))
            
            #Remove worker from death workers
            yield Worker.remove(key)
            
            #Remove own queue of worker
            queue = Queue(name)
            yield queue.empty()
    
    @defer.inlineCallbacks
    def processBadAssignedWorkers(self):
        assigned_workers = yield GoogleUser.get_assigned_workers()
        
        running_workers = yield Worker.getWorkers(Worker.redis_workers_keys)
        running_workers = [worker.get('name') for worker in running_workers if not worker.get('name') is None]
        
        death_workers = yield Worker.getWorkers(Worker.redis_death_workers_keys)
        death_workers = [worker.get('name') for worker in death_workers if not worker.get('name') is None]

        registered_workers = set(running_workers + death_workers)
        assigned_workers = set(assigned_workers)
        bad_workers = assigned_workers.difference(registered_workers)
        
        if bad_workers:
            self.log.warning('BAD_WORKERS %s are assigned to users. Running %s Death %s', bad_workers, len(running_workers), len(death_workers))
            for worker in bad_workers:
                bad_users = yield GoogleUser.get_connected(worker_name=worker)
                total_bad_users = len(bad_users)
                if total_bad_users > 0:
                    self.log.info('Reconnecting %s users assigned to bad worker %s', total_bad_users, worker)
                last_worker_index = total_bad_users-1
                for i in xrange(total_bad_users):
                    try:
                        data = bad_users[i]
                        user = GoogleUser(**data)
                        user.worker = user.userid
                        yield user.save()

                        reactor.callLater(0, self.reloginUser, user, worker, i==last_worker_index)
                        self.log.info('[%s] Reconnecting %s/%s user(s) of worker %s', user.userid, i+1, total_bad_users, worker)
                    except Exception as e:
                        self.log.err(e, '[%s] Exception while reconnecting'%(data['_userid']))

    
    @defer.inlineCallbacks
    def checkWorkers(self):
        try:
            for task in self._checkworkerstasks:
                if self.running:
                    yield task()
                else:
                    self.log.info('CheckWorkers task %s not launched. Supervisor not running', task)
        except Exception as e:
            self.log.err(e, 'Exception in checkWorkers task %s'%(task))
    
    @defer.inlineCallbacks
    def disconnectAwayUsers(self):
        away_users = yield GoogleUser.get_away()
        away_users  = [] if not away_users else away_users
        self.log.info('CHECKING_AWAY_USERS: %s', len(away_users))
        for data in away_users:
            try:
                user = GoogleUser(**data)
                API(user.userid, queue=user.worker).disconnect(user.userid)
                APNSAPI(user.userid).sendpush(message=u'{0} {1}'.format(u'\ue252', translate.TRANSLATORS[user.lang]._('disconnected')), token=user.pushtoken, badgenumber=user.badgenumber, sound='')
                self.DISCONNECT_AWAY_METRIC.add(1)
            except Exception as e:
                self.log.err(e, '[%s] Exception disconnecting user'%(data['_userid']))
    
    @defer.inlineCallbacks
    def reconnectUsers(self):
        connected_users = yield GoogleUser.get_connected()
        total_users = len(connected_users)
        self.log.info('reconnectUsers reconnecting %s users', total_users)
        for i in xrange(total_users):
            data = connected_users[i]
            try:
                user = GoogleUser(**data)
                worker, user.worker = user.worker, user.userid
                yield user.save()

                #Enqueing in the next loop iteration of twisted event loop
                reactor.callLater(0, self.reloginUser, user, user.worker)
                self.log.info('[%s] Reconnecting %s/%s user(s)', user.userid, i+1, total_users)
            except Exception as e:
                self.log.err(e, '[%s] Exception while reconnecting'%(data['_userid']))

    @defer.inlineCallbacks
    def reloginUser(self, user, last_worker, removeWorker=False):
        try:
            pending_jobs = yield self.getPendingJobs(user.userid, last_worker)
            yield API(user.userid).relogin(user, pending_jobs)
            if removeWorker:
                #Remove worker from death workers
                worker = Worker(queues=[], name=last_worker)
                yield worker.remove(worker.key)

                #Remove own queue of worker
                queue = Queue(worker.key)
                yield queue.empty()
        except Exception as e:
            self.log.err(e, '[%s] Exception while reconnecting'%(data['_userid']))

    def startService(self):
        Supervisor.startService(self)
        
        t = LoopingCall(self.disconnectAwayUsers)
        self.registerTask(t)
        t.start(conf.TASK_DISCONNECT_SECONDS, now = False)
        
        if conf.TASK_RECONNECT_ALL_USERS:
            reactor.callLater(conf.TWISTED_WARMUP, self.lock.run, self.reconnectUsers)
        else:
            reactor.callLater(conf.TWISTED_WARMUP, self.lock.run, self.processDeathWorkers)
        
        if conf.REDIS_WORKERS>0:
            t = LoopingCall(self.lock.run, self.checkWorkers)
            self.registerTask(t)
            t.start(conf.TASK_CHECK_WORKERS, now = False)
        
        reactor.callLater(conf.TWISTED_WARMUP, self._attach_global_metrics)
        