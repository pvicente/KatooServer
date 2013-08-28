'''
Created on Aug 7, 2013

@author: pvicente
'''
from katoo import KatooApp, conf
from katoo.apns.api import KatooAPNSService
from katoo.rqtwisted import worker
from katoo.supervisor import HerokuUnidlingSupervisor, MetricsSupervisor, \
    XMPPKeepAliveSupervisor
from katoo.utils.applog import getLoggerAdapter, getLogger
from katoo.utils.multiprocess import MultiProcess
from katoo.web import app
from socket import AF_INET
from twisted.internet import reactor
import os

application = KatooApp().app

if conf.ADOPTED_STREAM is None:
    stream = reactor.listenTCP(port=conf.PORT, factory=app, backlog=conf.BACKLOG, interface=conf.LISTEN)
    os.environ['ADOPTED_STREAM']=str(stream.fileno())
    
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
    w=worker.Worker([conf.MACHINEID, conf.DIST_QUEUE_LOGIN, conf.DIST_QUEUE_RELOGIN, conf.DIST_QUEUE_PUSH], name=conf.MACHINEID, loops=conf.REDIS_WORKERS, default_result_ttl=conf.DIST_DEFAULT_TTL, default_warmup=conf.TWISTED_WARMUP)
    w.log = getLoggerAdapter(getLogger('WORKER', level='INFO'), id='WORKER')
    w.setServiceParent(application)