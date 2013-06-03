'''
Created on Jun 3, 2013

@author: pvicente
'''
# coding: utf-8
# twisted application: foobar.tac

from twisted.application import service, internet
import cyclone.web
import os

class MainHandler(cyclone.web.RequestHandler):
    def get(self):
        self.write("Hello, world")


class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
        ]

        settings = dict(
            xheaders=False,
            static_path="./static",
            templates_path="./templates",
        )
        
        cyclone.web.Application.__init__(self, handlers, **settings)

class IndexHandler(cyclone.web.RequestHandler):
    def get(self):
        self.write("hello world")

application = service.Application("Application")

webservice = internet.TCPServer(int(os.getenv('PORT', 8888)), Application(), interface=os.getenv('LISTTEN', "0.0.0.0")) 
webservice.setServiceParent(application)

from katoo.utils.redis import RedisMixin
from katoo.rqtwisted.worker import Worker

RedisMixin.setup()

blocking_seconds = int(os.getenv('DEQUEUE_BLOCKTIME', 1))
workers = int(os.getenv('WORKERS', 1))

for i in xrange(workers):
    t = Worker(['default'])
    t.setServiceParent(application)