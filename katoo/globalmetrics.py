'''
Created on Aug 25, 2013

@author: pvicente
'''
from datetime import timedelta
from katoo import conf
from katoo.data import GoogleMessage, GoogleRosterItem, GoogleUser
from katoo.metrics import Metric
from katoo.rqtwisted.queue import Queue, FailedQueue
from katoo.utils.applog import getLogger, getLoggerAdapter
from katoo.utils.connections import RedisMixin
from katoo.utils.patterns import Observer
from katoo.utils.time import Timer
from twisted.internet import defer


log = getLoggerAdapter(getLogger(__name__),id='GLOBAL_METRICS')

class RedisMetrics(Observer):
    SOURCE='REDIS'
    UNIT='keys'
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
    def notify(self):
        keys = yield self._connection.dbsize()
        self._keys.add(keys)
        for key in self._items:
            queue = Queue(name=key, connection=self._connection)
            items = yield queue.count
            self._items[key].add(items)

class MongoMetrics(Observer):
    SOURCE='MONGO'
    
    def _create_metrics(self, collectionName):
        return {'count': Metric(name='%s.documents'%(collectionName), value=None, unit='documents', source='MONGO'),
                'avgObjSize': Metric(name='%s.document_size'%(collectionName), value=None, unit=conf.MONGO_STORAGE_UNIT, source='MONGO', scale=conf.MONGO_STORAGE_UNIT_SCALE), 
                'size': Metric(name='%s.size'%(collectionName), value=None, unit=conf.MONGO_STORAGE_UNIT, source='MONGO', scale=conf.MONGO_STORAGE_UNIT_SCALE),
                'storageSize': Metric(name='%s.storage_size'%(collectionName), value=None, unit=conf.MONGO_STORAGE_UNIT, source='MONGO', scale=conf.MONGO_STORAGE_UNIT_SCALE),
                'nindexes': Metric(name='%s.indexes'%(collectionName), value=None, unit='indexes', source='MONGO'),
                'totalIndexSize': Metric(name='%s.index_size'%(collectionName), value=None, unit=conf.MONGO_STORAGE_UNIT, source='MONGO', scale=conf.MONGO_STORAGE_UNIT_SCALE)
                }
    
    @defer.inlineCallbacks
    def _init_metrics_versions(self, name, key):
        versions = yield GoogleUser.get_distinct(key, spec={'_connected': True})
        self._versions[key] = dict([(version, Metric(name='%s.%s'%(name,version), value=None, unit='versions', source='MONGO')) for version in versions])
    
    def __init__(self):
        self._models = [GoogleMessage.model, GoogleRosterItem.model, GoogleUser.model]
        self._metrics = dict([(model.collection, self._create_metrics(model.collection)) for model in self._models])
        self._user_metrics = {'connected': Metric(name='googleusers.connected', value=None, unit='users', source='MONGO'),
                              'away': Metric(name='googleusers.away', value=None, unit='users', source='MONGO'),
                              'onLine': Metric(name='googleusers.onLine', value=None, unit='users', source='MONGO'),
                              'disconnected': Metric(name='googleusers.disconnected', value=None, unit='users', source='MONGO'),
                              'onRelogin': Metric(name='googleusers.onRelogin', value=None, unit='users', source='MONGO'),
                              'nopushtoken': Metric(name='googleusers.nopushtoken', value=None, unit='users', source='MONGO'),
                              'runningago24': Metric(name='googleusers.running24hago', value=None, unit='users', source='MONGO'),
                              'runningago12': Metric(name='googleusers.running12hago', value=None, unit='users', source='MONGO'),
                              'runningago01': Metric(name='googleusers.running1hago', value=None, unit='users', source='MONGO')
                              }
        
        self._global_metrics = {'objects': Metric(name='documents', value=None, unit='documents', source='MONGO'),
                                'avgObjSize': Metric(name='document_size', value=None, unit=conf.MONGO_STORAGE_UNIT, source='MONGO', scale=conf.MONGO_STORAGE_UNIT_SCALE),
                                'dataSize': Metric(name='size', value=None, unit=conf.MONGO_STORAGE_UNIT, source='MONGO', scale=conf.MONGO_STORAGE_UNIT_SCALE),
                                'storageSize': Metric(name='storage_size', value=None, unit=conf.MONGO_STORAGE_UNIT, source='MONGO', scale=conf.MONGO_STORAGE_UNIT_SCALE),
                                'fileSize': Metric(name='file_size', value=None, unit=conf.MONGO_STORAGE_UNIT, source='MONGO', scale=conf.MONGO_STORAGE_UNIT_SCALE),
                                'indexes': Metric(name='indexes', value=None, unit='indexes', source='MONGO'),
                                'indexSize': Metric(name='index_size', value=None, unit=conf.MONGO_STORAGE_UNIT, source='MONGO', scale=conf.MONGO_STORAGE_UNIT_SCALE)
                                }
        
        self._user_queries = {'connected': {'_connected': True},
                              'away': {'_connected': True, '_away': True},
                              'onLine': {'_connected': True, '_away': False},
                              'disconnected': {'_connected': False},
                              'onRelogin': {'_connected': True, '_onReloging': True},
                              'nopushtoken':{'_connected': True, '_pushtoken': ''},
                              'runningago24': None,
                              'runningago12': None,
                              'runningago01': None
                              }
        
        self._versions  = {}
        for name, key in [('katoo', '_version'), ('ios', '_iosversion'), ('hwmodel', '_hwmodel')]:
            self._init_metrics_versions(name, key)
    
    @defer.inlineCallbacks
    def notify(self):
        stats = yield GoogleUser.model.stats(collection_stats=False)
        log.debug('MONGO_STATS global. %s', stats)
        for key in self._global_metrics:
            self._global_metrics[key].add(stats.get(key, 0.0))
        
        for model in self._models:
            stats = yield model.stats()
            log.debug('MONGO_STATS for %s. %s', model.collection, stats)
            metrics = self._metrics[model.collection]
            for key in metrics:
                metrics[key].add(stats.get(key, 0.0))
        
        for query_key in self._user_queries:
            query = self._user_queries.get(query_key, None)
            if query is None:
                if query_key.find('running') == 0:
                    timeago = Timer().utcnow() - timedelta(hours=int(query_key[-2:]))
                    query = {'_connected': True, '_lastTimeConnected': {'$gte': timeago}}
            count = yield GoogleUser.model.count(query)
            self._user_metrics[query_key].add(count)
        
        for key_name, data in self._versions.iteritems():
            for key, metric in data.iteritems():
                count = yield GoogleUser.model.count(spec={key_name: key, '_connected': True})
                metric.add(count)
    