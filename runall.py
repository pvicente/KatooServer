'''
Created on Jun 4, 2013

@author: pvicente
'''
from twisted.application import internet
from katoo.rqtwisted.worker import Worker
from katoo.web import app
from katoo import conf, KatooApp

application = KatooApp().app
webservice = internet.TCPServer(conf.PORT, app, interface=conf.LISTEN) 
webservice.setServiceParent(application)
w=Worker(['default'])
w.setServiceParent(application)