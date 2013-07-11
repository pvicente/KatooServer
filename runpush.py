'''
Created on Jul 8, 2013

@author: pvicente
'''
from katoo import conf, KatooApp
from katoo.rqtwisted.worker import Worker
from katoo.supervisor import LocalSupervisor
from katoo.utils.applog import getLoggerAdapter, getLogger

application = KatooApp().app

supervisor = LocalSupervisor()
supervisor.setServiceParent(application)

if conf.REDIS_WORKERS > 0:
    w=Worker([conf.DIST_QUEUE_PUSH], name="PUSH-%s"%(conf.MACHINEID), loops=conf.REDIS_WORKERS, default_result_ttl=conf.DIST_DEFAULT_TTL, default_warmup=conf.TWISTED_WARMUP)
    w.log = getLoggerAdapter(getLogger('WORKER', level='INFO'), id='WORKER-%s'%(conf.MACHINEID))
    w.setServiceParent(application)