'''
Created on Jun 4, 2013

@author: pvicente
'''
from twisted.application import internet
from katoo.rqtwisted.worker import Worker
from katoo.web import app
from katoo import conf, KatooApp
from katoo.txapns.txapns.apns import APNSService

application = KatooApp().app
webservice = internet.TCPServer(conf.PORT, app, interface=conf.LISTEN) 
webservice.setServiceParent(application)

if conf.REDIS_WORKERS > 0:
    w=Worker(['default'])
    w.setServiceParent(application)

apns = APNSService(cert_path=conf.APNS_CERT, environment=conf.APNS_SANDBOX, timeout=conf.APNS_TIMEOUT)
apns.setName(conf.APNSERVICE_NAME)
apns.setServiceParent(application)