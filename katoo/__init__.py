from katoo import conf
from katoo.metrics import IncrementMetric
from katoo.rqtwisted import job, worker
from katoo.utils.applog import TwistedLogging
from katoo.utils.connections import RedisMixin, MongoMixin
from katoo.utils.decorators import inject_decorators
from katoo.utils.patterns import Singleton
from twisted.application import service
from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning

def newreactorstop():
    """Ignore ReactorNotRunning exception"""
    try:
        return KatooApp().oldreactorstop()
    except ReactorNotRunning:
        pass
    
class KatooApp(Singleton):
    def constructor(self):
        RedisMixin.setup()
        MongoMixin.setup()
        self.app = service.Application('KatooApp')
        self.service = self.app.getComponent(service.IService, None)
        self.log = TwistedLogging(self.app)
        self.oldreactorstop = reactor.stop
        reactor.stop = newreactorstop

    def getService(self, name):
        try:
            return self.service.getServiceNamed(name)
        except KeyError:
            return None
    
    def start(self):
        self.service.startService()
    
    def stop(self):
        self.service.stopService()
    
    def __iter__(self):
        return iter(self.service)

@inject_decorators(method_decorator_dict={'perform': IncrementMetric(name='jobs_performed', unit='jobs', source='RQTWISTED')})
class KatooJob(job.Job):
    pass

@inject_decorators(method_decorator_dict={'callback_perform_job': IncrementMetric(name='jobs_ok', unit='jobs', source='RQTWISTED'), 
                                          'errback_perform_job': IncrementMetric(name='jobs_failed', unit='jobs', source='RQTWISTED', reset=False),
                                          'work': IncrementMetric(name='workers_running', unit='workers', source='RQTWISTED', reset=False),
                                          'register_birth': IncrementMetric(name='live_workers', unit='workers', source='RQTWISTED', reset=False),
                                          'register_death': IncrementMetric(name='death_workers', unit='workers', source='RQTWISTED', reset=False)
                                          })
class KatooWorker(worker.Worker):
    pass

KatooApp()