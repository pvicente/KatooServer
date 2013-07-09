'''
Created on Jun 12, 2013

@author: pvicente
'''
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

class LocalSupervisor(service.Service):
    name='LOCAL-SUPERVISOR'
    log = getLoggerAdapter(log, id='%s-%s'%(name, conf.MACHINEID))
    
    @defer.inlineCallbacks
    def avoidHerokuUnidling(self, url):
        self.log.info('AVOIDING HEROKU IDLING: %s', url)
        yield cyclone.httpclient.fetch(url)
    
    def startService(self):
        if not conf.HEROKU_UNIDLING_URL is None:
            t = LoopingCall(self.avoidHerokuUnidling, conf.HEROKU_UNIDLING_URL)
            t.start(1800, now = True)
        return service.Service.startService(self)

class GlobalSupervisor(service.Service):
    name = 'GLOBAL_SUPERVISOR'
    log = getLoggerAdapter(log, id='%s-%s'%(name, conf.MACHINEID))
    
    def __init__(self):
        self.checkingWorkers = False
    
    @defer.inlineCallbacks
    def checkDeathWorkers(self):
        if not self.checkingWorkers:
            try:
                self.checkingWorkers = True
                yield self.processDeathWorkers()
            finally:
                self.checkingWorkers = False
    
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
            if conf.DIST_QUEUE_LOGIN in worker.get('queues'):
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
                    except Exception as e:
                        self.log.error('[%s] Exception %s reconnecting user', data['_userid'], e)
                    if i % 10:
                        self.log.info('Reconnected %s/%s of worker %s', i, total_users, name)
            
            #Remove worker from death workers
            Worker.remove(key)
            
            #Remove own queue of worker
            queue = Queue(name)
            yield queue.empty()

    @defer.inlineCallbacks
    def reconnectUsers(self):
        connected_users = yield GoogleUser.get_connected()
        self.log.info('RECONNECTING_USERS: %s', len(connected_users))
        for data in connected_users:
            try:
                user = GoogleUser(**data)
                yield API(user.userid).login(user)
            except Exception as e:
                self.log.error('Exception %s reconnecting user %s', e, data['_userid'])
    
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
                self.log.error('Exception %s disconnecting user %s', e, data['_userid'])
    
    
    def startService(self):
        if conf.TASK_RECONNECT_ALL_USERS:
            reactor.callLater(conf.TWISTED_WARMUP, self.reconnectUsers)
        t = LoopingCall(self.checkDeathWorkers)
        t.start(conf.TASK_DEATH_WORKERS, now = False)
        t = LoopingCall(self.disconnectAwayUsers)
        t.start(conf.TASK_DISCONNECT_SECONDS, now = False)
        return service.Service.startService(self)
