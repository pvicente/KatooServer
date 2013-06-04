'''
Created on May 29, 2013

@author: pvicente
'''
from cyclone import redis
from cyclone.redis import ResponseError, RedisFactory
from katoo import conf
from twisted.internet import defer
from twisted.python import log
from urlparse import urlparse


def url_parse(url, scheme='redis'):
    url = urlparse(url)
    
    # We only support redis:// schemes.
    assert url.scheme == scheme or not url.scheme
    
    # Extract the database ID from the path component if hasn't been given.
    try:
        db = int(url.path.replace('/', ''))
    except (AttributeError, ValueError):
            db = 0
    
    return (url.hostname, url.port or 6379, db, url.password)

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
    db = None

    @classmethod
    def setup(cls):
        if cls.redis_conn is None:
            hostname, port, db, password = url_parse(conf.REDIS_URL)
            AuthRedisProtocol.password = password
            RedisFactory.protocol = AuthRedisProtocol
            #pending to resolve Authentication with redis in cyclone.redis library
            cls.redis_conn = redis.lazyConnectionPool(host=hostname, port=port, dbid=db, poolsize=conf.REDIS_POOL)
            cls.db = db

