'''
Created on Aug 25, 2013

@author: pvicente
'''
from katoo import conf
from katoo.metrics import Metric
from katoo.rqtwisted.queue import Queue, FailedQueue
from katoo.utils.connections import RedisMixin
from twisted.internet import defer


class GlobalMetric(object):
    def register(self, service):
        service.register(self)
    
    def report(self):
        raise NotImplementedError()

class RedisMetrics(GlobalMetric):
    SOURCE='REDIS'
    UNIT='items'
    def __init__(self):
        self._connection = RedisMixin.redis_conn
        self._keys=Metric(name="keys", value=None, unit=self.UNIT, source=self.SOURCE)
        failed_queue_name = FailedQueue().name
        self._items={conf.DIST_QUEUE_LOGIN: Metric(name='queue_%s'%(conf.DIST_QUEUE_LOGIN), value=None, unit=self.UNIT, source=self.SOURCE),
                     conf.DIST_QUEUE_PUSH: Metric(name='queue_%s'%(conf.DIST_QUEUE_PUSH), value=None, unit=self.UNIT, source=self.SOURCE), 
                     conf.DIST_QUEUE_RELOGIN: Metric(name='queue_%s'%(conf.DIST_QUEUE_RELOGIN), value=None, unit=self.UNIT, source=self.SOURCE),
                     failed_queue_name: Metric(name='queue_%s'%(failed_queue_name), value=None, unit=self.UNIT, source=self.SOURCE)
                     }
    
    @defer.inlineCallbacks
    def report(self):
        keys = yield self._connection.dbsize()
        self._keys.add(keys)
        for key in self._items:
            queue = Queue(name=key, connection=self._connection)
            items = yield queue.count
            self._items[key].add(items)
    