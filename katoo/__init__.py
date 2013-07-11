from katoo import conf
from katoo.utils.applog import TwistedLogging
from katoo.utils.connections import RedisMixin, MongoMixin
from katoo.utils.patterns import Singleton
from twisted.application import service

class KatooApp(Singleton):
    def constructor(self):
        RedisMixin.setup()
        MongoMixin.setup()
        self.app = service.Application('KatooApp')
        self.service = self.app.getComponent(service.IService, None)
        self.log = TwistedLogging(self.app, fmt=conf.LOG_FORMAT, level=conf.LOG_LEVEL)

    def getService(self, name):
        try:
            return self.service.getServiceNamed(name)
        except KeyError:
            return None
    
    def getAPNService(self):
        return self.getService(conf.APNSERVICE_NAME)
    
    def start(self):
        self.service.startService()
    
    def stop(self):
        self.service.stopService()
    
    def __iter__(self):
        return iter(self.service)

KatooApp()