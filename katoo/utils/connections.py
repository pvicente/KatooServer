'''
Created on May 29, 2013

@author: pvicente
'''
from cyclone import redis
from cyclone.redis import ResponseError, RedisFactory
from katoo import conf
from twisted.internet import defer
from twisted.python import log
from txmongo._pymongo import helpers
from txmongo._pymongo.son import SON
from txmongo.collection import Collection
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

class AuthRedisProtocol(redis.RedisProtocol):
    password = None
    
    @defer.inlineCallbacks
    def connectionMade(self):
        if not self.password is None:
            try:
                yield self.auth(self.password)
            except ResponseError, e:
                self.factory.continueTrying = False
                self.transport.loseConnection()
                msg = "Redis AuthError.%s: %s"%(e.__class__.__name__,e)
                self.factory.connectionError(msg)
                if self.factory.isLazy:
                    log.msg(msg)
                defer.returnValue(None)
            else:
                yield redis.RedisProtocol.connectionMade(self)
        else:
            yield redis.RedisProtocol.connectionMade(self)

class RedisMixin(object):
    redis_conn = None
    redis_db = None

    @classmethod
    def setup(cls, url=None):
        if cls.redis_conn is None:
            if url is None:
                url = conf.REDIS_URL
            hostname, port, db, _, password = url_parse(url, 'redis')
            cls.redis_db = int(db)
            AuthRedisProtocol.password = password
            RedisFactory.protocol = AuthRedisProtocol
            cls.redis_conn = redis.lazyConnectionPool(host=hostname, port=port, dbid=cls.redis_db, poolsize=conf.REDIS_POOL, reconnect=True)


class AuthMongoProtocol(txmongo.MongoProtocol):
    username=None
    password=None
    database=None
    
    def _authenticate(self, name, password):
        """
        Send an authentication command for this database.
        mostly stolen from pymongo
        """
        if not isinstance(name, basestring):
            raise TypeError("name must be an instance of basestring")
        if not isinstance(password, basestring):
            raise TypeError("password must be an instance of basestring")
    
        d = defer.Deferred()
        # First get the nonce
        Collection(self.database, "$cmd").find_one({"getnonce": 1}, _proto=self
                ).addCallback(self._authenticate_with_nonce, name, password, d
                ).addErrback(d.errback)
    
    
        return d

    def _authenticate_with_nonce(self, result, name, password, d):
        nonce = result['nonce']
        key = helpers._auth_key(nonce, name, password)
    
        # hacky because order matters
        auth_command = SON(authenticate=1)
        auth_command['user'] = unicode(name)
        auth_command['nonce'] = nonce
        auth_command['key'] = key
    
        # Now actually authenticate
        Collection(self.database, "$cmd").find_one(auth_command,_proto=self
                ).addCallback(self._authenticated, d
                ).addErrback(d.errback)
    
    def _authenticated(self, result, d):
        """might want to just call callback with 0.0 instead of errback"""
        ok = result['ok']
        if ok:
            d.callback(ok)
        else:
            d.errback(result['errmsg'])
    
    @defer.inlineCallbacks
    def connectionMade(self):
        if not self.username is None:
            yield self._authenticate(self.username, self.password)
        yield txmongo.MongoProtocol.connectionMade(self)
    
class MongoMixin(object):
    mongo_conn = None
    mongo_db = None
    
    @classmethod
    def setup(cls, url=None):
        if cls.mongo_conn is None:
            if url is None:
                url = conf.MONGO_URL
            hostname, port, cls.mongo_db, username, password = url_parse(url, 'mongodb')
            AuthMongoProtocol.database = cls.mongo_db
            AuthMongoProtocol.username = username
            AuthMongoProtocol.password = password
            txmongo._MongoFactory.protocol = AuthMongoProtocol
            cls.mongo_conn = txmongo.lazyMongoConnectionPool(host=hostname, port=port, reconnect=True, pool_size=conf.MONGO_POOL)
    

