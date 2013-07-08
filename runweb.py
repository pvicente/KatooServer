'''
Created on Jul 8, 2013

@author: pvicente
'''
from katoo import conf, KatooApp
from katoo.supervisor import LocalSupervisor
from katoo.web import app
from twisted.application import internet

application = KatooApp().app
webservice = internet.TCPServer(conf.PORT, app, interface=conf.LISTEN) 
webservice.setServiceParent(application)

supervisor = LocalSupervisor()
supervisor.setServiceParent(application)