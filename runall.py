'''
Created on Aug 7, 2013

@author: pvicente
'''
from katoo import conf, KatooApp
from katoo.apns.api import KatooAPNSService
from katoo.rqtwisted import worker
from katoo.supervisor import HerokuUnidlingSupervisor, GlobalSupervisor,\
    MetricsSupervisor, XMPPKeepAliveSupervisor
from katoo.utils.applog import getLoggerAdapter, getLogger
from katoo.utils.multiprocess import MultiProcess
from katoo.utils.time import  sleep
from katoo.web import app
from socket import AF_INET
from twisted.internet import reactor
import os

#===============================================================================
#from twisted.application import internet

#Running cyclone as service in monocore. Deprecated with multiprocess support
# webservice = internet.TCPServer(conf.PORT, app, interface=conf.LISTEN) 
# webservice.setServiceParent(application)
#===============================================================================

application = KatooApp().app

worker_queues = [conf.MACHINEID, conf.DIST_QUEUE_LOGIN, conf.DIST_QUEUE_RELOGIN, conf.DIST_QUEUE_PUSH]

if conf.ADOPTED_STREAM is None:
    stream = reactor.listenTCP(port=conf.PORT, factory=app, backlog=conf.BACKLOG, interface=conf.LISTEN)
    os.environ['ADOPTED_STREAM']=str(stream.fileno())
    
    supervisor = GlobalSupervisor()
    supervisor.setServiceParent(application)
    
    heroku_unidling_supervisor = HerokuUnidlingSupervisor()
    heroku_unidling_supervisor.setServiceParent(application)
    
    if conf.MULTIPROCESS>0:
        m=MultiProcess(__file__, number=conf.MULTIPROCESS, fds=[stream.fileno()])
        m.setServiceParent(application)
else:
    reactor.adoptStreamPort(int(conf.ADOPTED_STREAM), AF_INET, app)

metrics_supervisor = MetricsSupervisor()
metrics_supervisor.setServiceParent(application)

xmpp_keepalive_supervisor = XMPPKeepAliveSupervisor()
xmpp_keepalive_supervisor.setServiceParent(application)

KatooAPNSService().service.setServiceParent(application)

if conf.REDIS_WORKERS > 0:
    worker.LOGGING_OK_JOBS = conf.LOGGING_OK_JOBS
    worker.SLEEP_CALL=sleep
    worker.MAX_RETRIES=conf.BACKEND_MAX_RETRIES
    worker.MAX_DELAY_TIME=conf.BACKEND_MAX_DELAY

    w=worker.Worker(worker_queues, name=conf.MACHINEID, loops=conf.REDIS_WORKERS, default_result_ttl=conf.DIST_DEFAULT_TTL,
                    default_warmup=conf.WORKER_WARMUP, default_enqueue_failed_jobs=conf.DIST_ENQUEUE_FAILED_JOBS,
                    default_perform_job_in_thread=conf.DIST_PERFORM_JOB_IN_THREAD, default_thread_pool_size=conf.DIST_THREAD_POOL)

    w.log = getLoggerAdapter(getLogger('WORKER', level='INFO'), id='WORKER')
    w.setServiceParent(application)