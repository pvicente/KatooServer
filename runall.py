'''
Created on Jun 4, 2013

@author: pvicente
'''
from katoo import conf, KatooApp
from katoo.apns.api import KatooAPNSService
from katoo.rqtwisted import worker
from katoo.supervisor import LocalSupervisor, GlobalSupervisor
from katoo.utils.applog import getLoggerAdapter, getLogger
from katoo.web import app
from twisted.application import internet

application = KatooApp().app
webservice = internet.TCPServer(conf.PORT, app, interface=conf.LISTEN) 
webservice.setServiceParent(application)

supervisor = LocalSupervisor()
supervisor.setServiceParent(application)

workers_supervisor = GlobalSupervisor()
workers_supervisor.setServiceParent(application)

KatooAPNSService().service.setServiceParent(application)

if conf.REDIS_WORKERS > 0:
    worker.LOGGING_OK_JOBS = conf.LOGGING_OK_JOBS
    w=worker.Worker([conf.MACHINEID, conf.DIST_QUEUE_LOGIN, conf.DIST_QUEUE_RELOGIN, conf.DIST_QUEUE_PUSH], name=conf.MACHINEID, loops=conf.REDIS_WORKERS, default_result_ttl=conf.DIST_DEFAULT_TTL, default_warmup=conf.TWISTED_WARMUP)
    w.log = getLoggerAdapter(getLogger('WORKER', level='INFO'), id='WORKER')
    w.setServiceParent(application)