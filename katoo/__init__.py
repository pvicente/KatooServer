from katoo import conf
from katoo.utils.applog import TwistedLogging
from katoo.utils.connections import RedisMixin, MongoMixin
from katoo.utils.patterns import Singleton
from twisted.application import service
from katoo.rqtwisted import job, worker
from katoo.utils.decorators import for_methods
from katoo.metrics import IncrementMetric

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
    
    def start(self):
        self.service.startService()
    
    def stop(self):
        self.service.stopService()
    
    def __iter__(self):
        return iter(self.service)

@for_methods(method_list=['perform'], decorator=IncrementMetric(name='jobs_performed', unit='jobs', source='rqtwisted'))
class KatooJob(job.Job):
    pass

@for_methods(method_list=['callback_perform_job'], decorator=IncrementMetric(name='jobs_ok', unit='jobs', source='rqtwisted'))
class KatooWorkerJobOk(worker.Worker):
    pass

@for_methods(method_list=['errback_perform_job'], decorator=IncrementMetric(name='jobs_failed', unit='jobs', source='rqtwisted'))
class KatooWorkerJobFailed(worker.Worker):
    pass

KatooApp()