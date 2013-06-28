from katoo import conf
from katoo.utils.applog import TwistedLogging
from katoo.utils.connections import RedisMixin, MongoMixin
from katoo.utils.patterns import Singleton
from twisted.application import service

def getLogger(name):
    return KatooApp().log.getLogger(name)

def getLoggerDefaultFormat(fmt=''):
    return "%s %s %s"%(conf.LOG_FORMAT, fmt,"%(message)s") if fmt else "%s %s"%(conf.LOG_FORMAT, "%(message)s")

class KatooApp(Singleton):
    def constructor(self):
        RedisMixin.setup()
        MongoMixin.setup()
        self.app = service.Application('KatooApp')
        self.service = self.app.getComponent(service.IService, None)
        self.log = TwistedLogging(self.app, fmt=getLoggerDefaultFormat(), level=conf.LOG_LEVEL)

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

KatooApp()