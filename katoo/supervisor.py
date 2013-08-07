'''
Created on Jun 12, 2013

@author: pvicente
'''
from datetime import datetime
from dateutil import parser
from katoo import conf
from katoo.api import API
from katoo.apns.api import API as APNSAPI
from katoo.data import GoogleUser
from katoo.rqtwisted.job import Job
from katoo.rqtwisted.queue import Queue
from katoo.rqtwisted.worker import Worker
from katoo.utils.applog import getLogger, getLoggerAdapter
from twisted.application import service
from twisted.internet import defer, reactor
from twisted.internet.task import LoopingCall
import cyclone.httpclient

log = getLogger(__name__, level='INFO')

class Supervisor(service.Service):
    def __init__(self):
        self.tasks = []
    
    def registerTask(self, t):
        self.tasks.append(t)
    
    def stopService(self, *args, **kwargs):
        for task in self.tasks:
            self.log.info('STOPPING_TASK %s', task)
            task.stop()
        return service.Service.stopService(self, *args, **kwargs)

class HerokuUnidlingSupervisor(Supervisor):
    name='HEROKU_UNIDLING_SUPERVISOR'
    log = getLoggerAdapter(log, id=name)
    
    @defer.inlineCallbacks
    def avoidHerokuUnidling(self, url):
        self.log.info('AVOIDING HEROKU IDLING: %s', url)
        yield cyclone.httpclient.fetch(url)
    
    def startService(self):
        if not conf.HEROKU_UNIDLING_URL is None:
            t = LoopingCall(self.avoidHerokuUnidling, conf.HEROKU_UNIDLING_URL)
            self.registerTask(t)
            t.start(1800, now = True)
        return service.Service.startService(self)

class GlobalSupervisor(Supervisor):
    name = 'GLOBAL_SUPERVISOR'
    log = getLoggerAdapter(log, id=name)
    
    def __init__(self):
        Supervisor.__init__(self)
        self.checkingMigrateUsers = False
    
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
            self.log.info('[%s] USER_MIGRATION_STOPPED %s second(s) ago. Performing new relogin ...', user.userid, delta_time.seconds)
            user.worker = user.userid
            user.onMigrationTime=''
            yield user.save()
            yield API(user.userid).relogin(user, pending_jobs=[])
    
    @defer.inlineCallbacks
    def getPendingJobs(self, userid, queue_name):
        queue = Queue(queue_name)
        job_ids = yield queue.job_ids
        jobs = []
        for job_id in job_ids:
            job = yield Job.fetch(job_id, connection=queue.connection)
            if job.meta.get('userid') == userid:
                jobs.append(job_id)
        defer.returnValue(jobs)
    
    @defer.inlineCallbacks
    def processDeathWorkers(self):
        death_workers = yield Worker.getWorkers(Worker.redis_death_workers_keys)
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
                for i in xrange(total_bad_users):
                    try:
                        data = bad_users[i]
                        user = GoogleUser(**data)
                        user.worker = user.userid
                        yield user.save()
                        
                        pending_jobs = yield self.getPendingJobs(user.userid, worker)
                        yield API(user.userid).relogin(user, pending_jobs)
                        self.log.info('[%s] Reconnected %s/%s user(s) of worker %s', user.userid, i+1, total_bad_users, worker)
                    except Exception as e:
                        self.log.err(e, '[%s] Exception while reconnecting'%(data['_userid']))
                    
            
                #Remove worker from death workers
                worker = Worker(queues=[], name=worker)
                yield worker.remove(worker.key)
                
                #Remove own queue of worker
                queue = Queue(worker)
                yield queue.empty()
    
    @defer.inlineCallbacks
    def disconnectAwayUsers(self):
        away_users = yield GoogleUser.get_away()
        away_users  = [] if not away_users else away_users
        self.log.info('CHECKING_AWAY_USERS: %s', len(away_users))
        for data in away_users:
            try:
                user = GoogleUser(**data)
                yield API(user.userid, queue=user.worker).disconnect(user.userid)
                yield APNSAPI(user.userid).sendcustom(lang=user.lang, token=user.pushtoken, badgenumber=user.badgenumber, type_msg='disconnect', sound='')
            except Exception as e:
                self.log.err(e, '[%s] Exception disconnecting user'%(data['_userid']))
    
    @defer.inlineCallbacks
    def reconnectUsers(self):
        if not self.checkingMigrateUsers:
            self.checkingMigrateUsers=True
            connected_users = yield GoogleUser.get_connected()
            self.log.info('RECONNECTING_USERS: %s', len(connected_users))
            for data in connected_users:
                try:
                    user = GoogleUser(**data)
                    user.worker = user.userid
                    yield user.save()
                    
                    yield API(user.userid).relogin(user, [])
                except Exception as e:
                    self.log.err(e, '[%s] Exception while reconnecting'%(data['_userid']))
            self.checkingMigrateUsers=False
    
    @defer.inlineCallbacks
    def checkMigrateUsers(self):
        if not self.checkingMigrateUsers:
            try:
                self.checkingMigrateUsers = True
                yield self.processOnMigrationUsers()
                yield self.processDeathWorkers()
                yield self.processBadAssignedWorkers()
            finally:
                self.checkingMigrateUsers = False
    
    @defer.inlineCallbacks
    def runningWorkers(self):
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
    def xmpp_keep_alive(self):
        workers = yield Worker.getWorkers(Worker.redis_workers_keys)
        if workers:
            self.log.info('XMPP_KEEP_ALIVE_TASK STARTED %s running worker(s)', len(workers))
        for worker in workers:
            name = worker.get('name')
            if name is None:
                self.log.warning('XMPP_KEEP_ALIVE_TASK worker data is wrong %s', worker)
                continue
            connected_users = yield GoogleUser.get_connected(name)
            total_users = len(connected_users)
            for i in xrange(total_users):
                    try:
                        data = connected_users[i]
                        user = GoogleUser(**data)
                        yield API(user.userid, queue=name).xmpp_send_keep_alive(user.userid)
                    except Exception as e:
                        self.log.err(e, '[%s] Exception while sending XMPP_KEEP_ALIVE'%(data['_userid']))
        if workers:
            self.log.info('XMPP_KEEP_ALIVE_TASK FINISHED %s running worker(s)', len(workers))
        
    
    def startService(self):
        t = LoopingCall(self.disconnectAwayUsers)
        self.registerTask(t)
        t.start(conf.TASK_DISCONNECT_SECONDS, now = False)
        
        if conf.TASK_RECONNECT_ALL_USERS:
            reactor.callLater(conf.TWISTED_WARMUP, self.reconnectUsers)
        
        if conf.REDIS_WORKERS>0:
            t = LoopingCall(self.checkMigrateUsers)
            self.registerTask(t)
            t.start(conf.TASK_DEATH_WORKERS, now = False)
            
            t = LoopingCall(self.runningWorkers)
            self.registerTask(t)
            t.start(conf.TASK_RUNNING_WORKERS, now = False)
        
        if conf.XMPP_KEEP_ALIVE_TIME > 0:
            t = LoopingCall(self.xmpp_keep_alive)
            self.registerTask(t)
            t.start(conf.XMPP_KEEP_ALIVE_TIME, now = False)
        
        return service.Service.startService(self)
