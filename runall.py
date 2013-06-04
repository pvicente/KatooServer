'''
Created on Jun 4, 2013

@author: pvicente
'''
from twisted.application import service, internet
from katoo.rqtwisted.worker import Worker
from katoo.web import app
import os

application = service.Application("runall")
webservice = internet.TCPServer(int(os.getenv('PORT', 8888)), app, interface=os.getenv('LISTEN', "0.0.0.0")) 
webservice.setServiceParent(application)
w=Worker(['default'])
w.setServiceParent(application)