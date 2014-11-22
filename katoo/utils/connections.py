'''
Created on May 29, 2013

@author: pvicente
'''
from cyclone import redis
from cyclone.redis import RedisFactory
from katoo import conf
from katoo.metrics import IncrementMetric, Metric
from katoo.utils.applog import getLoggerAdapter, getLogger
from katoo.utils.decorators import inject_decorators
from twisted.internet import defer, reactor
from twisted.python import log
#from txmongo._pymongo import helpers
#from txmongo._pymongo.son import SON
#from txmongo.collection import Collection
from urlparse import urlparse
import txmongo

def url_parse(url, scheme):
    url = urlparse(url)
    
    # We only support redis:// schemes.
    assert url.scheme == scheme or not url.scheme
    
    # Extract the database ID from the path component if hasn't been given.
    try:
        db = url.path.replace('/', '')
        if not db:
            db = "0"
    except (AttributeError, ValueError):
            db = "0"
    
    return (url.hostname, url.port or 6379, db, url.username, url.password)

@inject_decorators(method_decorator_dict={ 'execute_command': IncrementMetric(name='execute_command', unit='calls', source='REDIS'),
                                           'replyReceived': IncrementMetric(name='replyReceived', unit='calls', source='REDIS'),
                                           'exists': IncrementMetric(name='op_exists', unit='calls', source='REDIS'),
                                           'hget': IncrementMetric(name='op_hget', unit='calls', source='REDIS'),
                                           'hgetall': IncrementMetric(name='op_hgetall', unit='calls', source='REDIS'),
                                           'hset': IncrementMetric(name='op_hset', unit='calls', source='REDIS'),
                                           'hmset': IncrementMetric(name='op_hmset', unit='calls', source='REDIS'),
                                           'delete': IncrementMetric(name='op_delete', unit='calls', source='REDIS'),
                                           'rpush': IncrementMetric(name='op_rpush', unit='calls', source='REDIS'),
                                           'lpop': IncrementMetric(name='op_lpop', unit='calls', source='REDIS'),
                                           'blpop': IncrementMetric(name='op_blpop', unit='calls', source='REDIS'),
                                           'expire': IncrementMetric(name='op_expire', unit='calls', source='REDIS')
                                          })
class AuthRedisProtocol(redis.RedisProtocol):
    CONNECTIONS_METRIC=Metric(name='connections', value=None, unit='connections', source='REDIS', reset=False)
    password = None
    log = None
    
    @IncrementMetric(name='connectionMade', unit='calls', source='REDIS')
    @defer.inlineCallbacks
    def connectionMade(self):
        self.CONNECTIONS_METRIC.add(1)
        if not self.password is None:
            try:
                yield self.auth(self.password)
                yield redis.RedisProtocol.connectionMade(self)
            except Exception, e:
                self.factory.maxRetries = conf.BACKEND_MAX_RETRIES
                self.factory.maxDelay = conf.BACKEND_MAX_DELAY
                self.transport.loseConnection()
                msg = "Redis Error.%s: %r"%(e.__class__.__name__, e)
                self.factory.connectionError(msg)
                self.log.warning(msg)
                defer.returnValue(None)
        else:
            yield redis.RedisProtocol.connectionMade(self)

        if not self.connected:
            #Avoid problem with RedisProtocol connectionMade
            self.factory.continueTrying = True
            self.factory.maxRetries = conf.BACKEND_MAX_RETRIES

        self.log.info('connectionMade and authenticated to REDIS id=%s connected=%d total=%d', hex(id(self)), self.connected, self.CONNECTIONS_METRIC)
    
    @IncrementMetric(name='connectionLost', unit='calls', source='REDIS')
    def connectionLost(self, why):
        self.CONNECTIONS_METRIC.add(-1)
        if reactor.running:
            logging_out = self.log.warning
        else:
            logging_out = self.log.info
        logging_out('connectionLost to REDIS id=%s total=%d reason=%r', hex(id(self)), self.CONNECTIONS_METRIC, why)
        return redis.RedisProtocol.connectionLost(self, why)

class RedisMixin(object):
    redis_conn = None
    redis_db = None
    log = None

    @classmethod
    def setup(cls, url=None, log=None):
        if cls.redis_conn is None:
            if url is None:
                url = conf.REDIS_URL
            hostname, port, db, _, password = url_parse(url, 'redis')
            cls.redis_db = int(db)
            AuthRedisProtocol.password = password
            if log is None:
                log = getLoggerAdapter(getLogger(__name__), id='REDIS_CONNECTIONPOOL')
            cls.log = AuthRedisProtocol.log = log
            RedisFactory.protocol = AuthRedisProtocol
            cls.redis_conn = redis.lazyConnectionPool(host=hostname, port=port, dbid=cls.redis_db, poolsize=conf.REDIS_POOL, reconnect=True)

@inject_decorators(method_decorator_dict={'sendMessage':  IncrementMetric(name='sendMessage', unit='calls', source='MONGO'),
                                          'dataReceived': IncrementMetric(name='dataReceived', unit='calls', source='MONGO'),
                                          'messageReceived':   IncrementMetric(name='messageReceived', unit='calls', source='MONGO'),
                                          'querySuccess':   IncrementMetric(name='querySuccess', unit='calls', source='MONGO'),
                                          'queryFailure':   IncrementMetric(name='queryFailure', unit='calls', source='MONGO', reset=False),
                                          'OP_INSERT': IncrementMetric(name='op_insert', unit='calls', source='MONGO'),
                                          'OP_UPDATE':     IncrementMetric(name='op_update', unit='calls', source='MONGO'),
                                          'OP_DELETE':   IncrementMetric(name='op_delete', unit='calls', source='MONGO'),
                                          'OP_KILL_CURSORS': IncrementMetric(name='op_kill_cursors', unit='calls', source='MONGO'),
                                          'OP_GET_MORE': IncrementMetric(name='op_get_more', unit='calls', source='MONGO'),
                                          'OP_QUERY': IncrementMetric(name='op_query', unit='calls', source='MONGO')
                                          })
# class AuthMongoProtocol(txmongo.MongoProtocol):
#     CONNECTIONS_METRIC=Metric(name='connections', value=None, unit='connections', source='MONGO', reset=False)
#     username=None
#     password=None
#     database=None
#     log = None
#
#     def _authenticate(self, name, password):
#         """
#         Send an authentication command for this database.
#         mostly stolen from pymongo
#         """
#         if not isinstance(name, basestring):
#             raise TypeError("name must be an instance of basestring")
#         if not isinstance(password, basestring):
#             raise TypeError("password must be an instance of basestring")
#
#         d = defer.Deferred()
#         # First get the nonce
#         Collection(self.database, "$cmd").find_one({"getnonce": 1}, _proto=self
#                 ).addCallback(self._authenticate_with_nonce, name, password, d
#                 ).addErrback(self._auth_error, d)
#
#
#         return d
#
#     def _authenticate_with_nonce(self, result, name, password, d):
#         nonce = result['nonce']
#         key = helpers._auth_key(nonce, name, password)
#
#         # hacky because order matters
#         auth_command = SON(authenticate=1)
#         auth_command['user'] = unicode(name)
#         auth_command['nonce'] = nonce
#         auth_command['key'] = key
#
#         # Now actually authenticate
#         Collection(self.database, "$cmd").find_one(auth_command,_proto=self
#                 ).addCallback(self._authenticated, d
#                 ).addErrback(self._auth_error, d)
#
#     def _authenticated(self, result, d):
#         """might want to just call callback with 0.0 instead of errback"""
#         ok = result['ok']
#         if ok:
#             d.callback(ok)
#         else:
#             d.errback(ValueError(result['errmsg']))
#
#     def _auth_error(self, reason):
#         self.log.warning("Auth error with Mongo reason=%s", reason)
#
#
#     @IncrementMetric(name='connectionMade', unit='calls', source='MONGO')
#     @defer.inlineCallbacks
#     def connectionMade(self):
#         self.CONNECTIONS_METRIC.add(1)
#         if not self.username is None:
#             try:
#                 yield self._authenticate(self.username, self.password)
#                 yield txmongo.MongoProtocol.connectionMade(self)
#             except Exception, e:
#                 self.factory.maxRetries = conf.BACKEND_MAX_RETRIES
#                 self.transport.loseConnection()
#                 msg = "Mongo Error.%s: %r"%(e.__class__.__name__, e)
#                 self.log.warning(msg)
#                 defer.returnValue(None)
#         else:
#             yield txmongo.MongoProtocol.connectionMade(self)
#
#         if not self.connected:
#             self.factory.continueTrying = True
#             self.factory.maxRetries = conf.BACKEND_MAX_RETRIES
#
#         self.log.info('connectionMade and authenticated to MONGO id=%s connected=%d total=%d', hex(id(self)), self.connected, self.CONNECTIONS_METRIC)
#
#
#     @IncrementMetric(name='connectionLost', unit='calls', source='MONGO')
#     def connectionLost(self, reason):
#         self.CONNECTIONS_METRIC.add(-1)
#         if reactor.running:
#             logging_out = self.log.warning
#         else:
#             logging_out = self.log.info
#         logging_out('connectionLost to MONGO id=%s total=%d reason=%r', hex(id(self)), self.CONNECTIONS_METRIC, reason)
#         return txmongo.MongoProtocol.connectionLost(self, reason)
    
class MongoMixin(object):
    mongo_conn = None
    mongo_db = None
    log = None
    
    @classmethod
    def setup(cls, url=None, log=None):
        if cls.mongo_conn is None:
            if url is None:
                url = conf.MONGO_URL
            hostname, port, cls.mongo_db, username, password = url_parse(url, 'mongodb')
            txmongo.connection._Connection.maxRetries = conf.BACKEND_MAX_RETRIES
            txmongo.connection._Connection.maxDelay = conf.BACKEND_MAX_DELAY
            cls.mongo_conn = txmongo.connection.ConnectionPool(url, pool_size=conf.MONGO_POOL)
    

