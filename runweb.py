'''
Created on Jul 8, 2013

@author: pvicente
'''
from katoo import conf, KatooApp
from katoo.utils.multiprocess import MultiProcess
from katoo.web import app
from socket import AF_INET
from twisted.internet import reactor
import os

#===============================================================================
#from twisted.application import internet

#Running cyclone as service in monocore. Deprecated with multiprocess support
# webservice = internet.TCPServer(conf.PORT, app, interface=conf.LISTEN) 
# webservice.setServiceParent(application)
#===============================================================================

application = KatooApp().app

if conf.ADOPTED_STREAM is None:
    stream = reactor.listenTCP(port=conf.PORT, factory=app, backlog=conf.BACKLOG, interface=conf.LISTEN)
    os.environ['ADOPTED_STREAM']=str(stream.fileno())
    
    if conf.MULTIPROCESS>0:
        m=MultiProcess(__file__, number=conf.MULTIPROCESS, fds=[stream.fileno()])
        m.setServiceParent(application)
else:
    reactor.adoptStreamPort(int(conf.ADOPTED_STREAM), AF_INET, app)
    

