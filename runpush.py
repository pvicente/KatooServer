'''
Created on Jul 8, 2013

@author: pvicente
'''
from katoo import conf, KatooApp
from katoo.apns import delivery
from katoo.rqtwisted.worker import Worker
from katoo.supervisor import LocalSupervisor
from katoo.txapns.txapns.apns import APNSService
from katoo.utils.applog import getLoggerAdapter, getLogger

application = KatooApp().app

supervisor = LocalSupervisor()
supervisor.setServiceParent(application)

delivery.APNS = APNSService(cert_path=conf.APNS_CERT, environment=conf.APNS_SANDBOX, timeout=conf.APNS_TIMEOUT)
delivery.APNS.setName(conf.APNSERVICE_NAME)
delivery.APNS.setServiceParent(application)

if conf.REDIS_WORKERS > 0:
    w=Worker([conf.DIST_QUEUE_PUSH], name="PUSH-%s"%(conf.MACHINEID), loops=conf.REDIS_WORKERS, default_result_ttl=conf.DIST_DEFAULT_TTL, default_warmup=conf.TWISTED_WARMUP)
    w.log = getLoggerAdapter(getLogger('WORKER', level='INFO'), id='WORKER-%s'%(conf.MACHINEID))
    w.setServiceParent(application)