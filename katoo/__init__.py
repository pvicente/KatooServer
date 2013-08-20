from katoo import conf
from katoo.metrics import IncrementMetric
from katoo.rqtwisted import job, worker
from katoo.txMongoModel.mongomodel import model
from katoo.utils.applog import TwistedLogging
from katoo.utils.connections import RedisMixin, MongoMixin
from katoo.utils.decorators import inject_decorators
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
    
    def start(self):
        self.service.startService()
    
    def stop(self):
        self.service.stopService()
    
    def __iter__(self):
        return iter(self.service)

@inject_decorators(method_decorator_dict={'perform': IncrementMetric(name='jobs_performed', unit='jobs', source='RQTWISTED')})
class KatooJob(job.Job):
    pass

@inject_decorators(method_decorator_dict={'callback_perform_job': IncrementMetric(name='jobs_ok', unit='jobs', source='RQTWISTED'), 'errback_perform_job': IncrementMetric(name='jobs_failed', unit='jobs', source='RQTWISTED')})
class KatooWorker(worker.Worker):
    pass

@inject_decorators(method_decorator_dict={'execute':  IncrementMetric(name='mongo_transaction', unit='calls', source='MONGO'), 
                                          'insert':   IncrementMetric(name='mongo_insert', unit='calls', source='MONGO'),
                                          'find_one': IncrementMetric(name='mongo_findone', unit='calls', source='MONGO'),
                                          'find':     IncrementMetric(name='mongo_find', unit='calls', source='MONGO'),
                                          'remove':   IncrementMetric(name='mongo_remove', unit='calls', source='MONGO'),
                                          'update':   IncrementMetric(name='mongo_update', unit='calls', source='MONGO')
                                          })
class KatooDataModel(model.Model):
    pass

KatooApp()