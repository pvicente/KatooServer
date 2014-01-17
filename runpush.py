'''
Created on Jul 8, 2013

@author: pvicente
'''
from katoo import conf, KatooApp
from katoo.apns.api import KatooAPNSService
from katoo.rqtwisted import worker
from katoo.supervisor import MetricsSupervisor
from katoo.utils.applog import getLoggerAdapter, getLogger
from katoo.utils.multiprocess import MultiProcess
import os

application = KatooApp().app

if conf.ADOPTED_STREAM is None:
    os.environ['ADOPTED_STREAM']='' #Avoid to perform Mutlprocess Service in child processes
    
    if conf.MULTIPROCESS>0:
        m=MultiProcess(__file__, number=conf.MULTIPROCESS)
        m.setServiceParent(application)

metrics_supervisor = MetricsSupervisor()
metrics_supervisor.setServiceParent(application)

KatooAPNSService().service.setServiceParent(application)

if conf.REDIS_WORKERS > 0:
    worker.LOGGING_OK_JOBS = conf.LOGGING_OK_JOBS
    w=worker.Worker([conf.DIST_QUEUE_PUSH], name="PUSH-%s"%(conf.MACHINEID), loops=conf.REDIS_WORKERS,
                    default_result_ttl=conf.DIST_DEFAULT_TTL, default_warmup=conf.WORKER_WARMUP, default_enqueue_failed_jobs=conf.DIST_ENQUEUE_FAILED_JOBS)
    w.log = getLoggerAdapter(getLogger('WORKER', level='INFO'), id='WORKER')
    w.setServiceParent(application)