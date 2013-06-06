'''
Created on Jun 4, 2013

@author: pvicente
'''

from cyclone.web import log
from katoo.api import login, logout, update
from katoo.data import XMPPGoogleUser
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.utils.connections import RedisMixin
from twisted.internet import defer
import cyclone.web
from cyclone.escape import json_encode

class RequiredArgument(object):
    pass

class DefaultArgument(object):
    pass

class arguments(object):
    ARGUMENTS = {}
    def __init__(self, handler):
        self.args = dict([(k,handler.get_argument(k)) if v is RequiredArgument else (k,handler.get_argument(k,v)) for k,v in self.ARGUMENTS.iteritems()])
        #Remove default arguments
        self.args = dict([(k,v) for k,v in self.args.iteritems() if not v is DefaultArgument])

class login_arguments(arguments):
    ARGUMENTS = dict([('token', RequiredArgument), ('refreshtoken', RequiredArgument), ('resource', RequiredArgument),
                      ('pushtoken', ''), ('badgenumber', 0), ('pushsound',''), ('lang','en-US')])

class update_arguments(arguments):
    ARGUMENTS = dict([('token', DefaultArgument), ('refreshtoken', DefaultArgument), ('resource', DefaultArgument),
                      ('pushtoken', DefaultArgument), ('badgenumber', DefaultArgument), ('pushsound',DefaultArgument), ('lang', DefaultArgument)])

class GoogleHandler(cyclone.web.RequestHandler, RedisMixin):
    
    def _response_json(self, value):
        self.set_header("Content-Type", "application/json")
        self.finish(json_encode(value))
    
    @defer.inlineCallbacks
    def get(self, key):
        user = yield XMPPGoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        self._response_json(user.toDict())
    
    @defer.inlineCallbacks
    def post(self, key):
        try:
            user = yield XMPPGoogleUser.load(key)
            if not user is None:
                self._response_json({'success': False, 'reason': 'Already logged'})
            else:
                args = login_arguments(self).args
                user = XMPPGoogleUser(userid=key, **args)
                yield login(user)
                self._response_json({'success': True, 'reason': 'ok'})
        except XMPPUserAlreadyLogged:
            self._response_json({'success': True, 'reason': 'ok'})
    
    @defer.inlineCallbacks
    def put(self, key):
        user = yield XMPPGoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        args = update_arguments(self).args
        try:
            yield update(key, **args)
            self._response_json({'success': True, 'reason': 'ok'})
        except XMPPUserNotLogged as e:
            raise cyclone.web.HTTPError(500, str(e))
    
    @defer.inlineCallbacks
    def delete(self, key):
        try:
            user = yield XMPPGoogleUser.load(key)
            if user is None:
                raise cyclone.web.HTTPError(404)
            yield logout(key)
            self._response_json({'success': True, 'reason': 'ok'})
        except XMPPUserNotLogged as e:
            #Remove user from database
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
