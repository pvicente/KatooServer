'''
Created on Jun 4, 2013

@author: pvicente
'''
from katoo import conf, KatooApp
from katoo.rqtwisted.worker import Worker
from katoo.web import app
from twisted.application import internet
from katoo.supervisor import Supervisor

application = KatooApp().app
webservice = internet.TCPServer(conf.PORT, app, interface=conf.LISTEN) 
webservice.setServiceParent(application)

supervisor = Supervisor()
supervisor.setServiceParent(application)

if conf.REDIS_WORKERS > 0:
    w=Worker(['default'])
    w.setServiceParent(application)