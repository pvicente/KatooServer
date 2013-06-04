'''
Created on Jun 4, 2013

@author: pvicente
'''

from katoo.utils.redis import RedisMixin
from twisted.internet import defer
import cyclone.web
from cyclone.web import log
import actions

class GoogleHandler(cyclone.web.RequestHandler, RedisMixin):
    @defer.inlineCallbacks
    def post(self, key):
        action = actions.login(key, self)
        yield action()
    
    @defer.inlineCallbacks
    def put(self, key):
        res = yield key
        log.msg('key: %s request: %s'%(res, vars(self.request)))
        self.finish('hello put: %s'%(res))
    
    @defer.inlineCallbacks
    def delete(self, key):
        res = yield key
        log.msg('key: %s request: %s'%(res, vars(self.request)))
        self.finish('hello delete: %s'%(res))

class GoogleMessagesHandler(cyclone.web.RequestHandler, RedisMixin):
    @defer.inlineCallbacks
    def get(self, key):
        res = yield key
        log.msg('key: %s request: %s'%(res, vars(self.request)))
        self.write('hello get: %s'%(res))
    
    @defer.inlineCallbacks
    def delete(self, key):
        res = yield key
        log.msg('key: %s request: %s'%(res, vars(self.request)))
        self.finish('hello delete: %s'%(res))
