'''
Created on Jun 4, 2013

@author: pvicente
'''

from cyclone.web import log
from katoo.api import login, logout
from katoo.data import XMPPGoogleUser
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.utils.connections import RedisMixin
from twisted.internet import defer
import cyclone.web
import json

class RequiredArgument(object):
    pass

class arguments(object):
    ARGUMENTS = {}
    def __init__(self, handler):
        self.args = dict([(k,handler.get_argument(k)) if v is RequiredArgument else (k,handler.get_argument(k,v)) for k,v in self.ARGUMENTS.iteritems()])

class login_arguments(arguments):
    ARGUMENTS = {'token': RequiredArgument, 'refreshtoken': RequiredArgument, 'resource': RequiredArgument, 
                 'pushtoken': '','badgenumber' : 0, 'pushsound': '', 'lang': 'en-US'}


class GoogleHandler(cyclone.web.RequestHandler, RedisMixin):
    @defer.inlineCallbacks
    def get(self, key):
        user = yield XMPPGoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        self.finish(json.dumps(user.toDict()))
    
    @defer.inlineCallbacks
    def post(self, key):
        try:
            user = yield XMPPGoogleUser.load(key)
            if not user is None:
                self.finish(json.dumps({'success': False, 'reason': 'Already logged'}))
            else:
                args = login_arguments(self).args
                user = XMPPGoogleUser(userid=key, **args)
                yield login(user)
                self.finish(json.dumps({'success': False, 'reason': 'ok'}))
        except XMPPUserAlreadyLogged:
            self.finish(json.dumps({'success': False, 'reason': 'Already logged'}))
    
    @defer.inlineCallbacks
    def put(self, key):
        res = yield key
        log.msg('key: %s request: %s'%(res, vars(self.request)))
        self.finish('hello put: %s'%(res))

    
    @defer.inlineCallbacks
    def delete(self, key):
        try:
            user = yield XMPPGoogleUser.load(key)
            if user is None:
                raise cyclone.web.HTTPError(404)
            yield logout(key)
            self.finish(json.dumps({'success': True, 'reason': 'ok'}))
        except XMPPUserNotLogged as e:
            yield user.remove(user.userid)
            raise cyclone.web.HTTPError(500, str(e))

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
