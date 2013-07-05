'''
Created on Jun 4, 2013

@author: pvicente
'''
from katoo import conf, KatooApp
from katoo.rqtwisted.worker import Worker
from katoo.web import app
from twisted.application import internet
from katoo.supervisor import Supervisor
from katoo.utils.applog import getLoggerAdapter, getLogger

application = KatooApp().app
webservice = internet.TCPServer(conf.PORT, app, interface=conf.LISTEN) 
webservice.setServiceParent(application)

supervisor = Supervisor()
supervisor.setServiceParent(application)

if conf.REDIS_WORKERS > 0:
    w=Worker([conf.MACHINEID, conf.DIST_QUEUE_LOGIN], name=conf.MACHINEID, loops=conf.REDIS_WORKERS)
    w.log = getLoggerAdapter(getLogger('WORKER', level='INFO'), id='WORKER-%s'%(conf.MACHINEID))
    w.setServiceParent(application)