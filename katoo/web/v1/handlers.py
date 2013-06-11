'''
Created on Jun 4, 2013

@author: pvicente
'''

from cyclone.escape import json_encode
from datetime import datetime
from katoo.api import login, logout, update
from katoo.data import GoogleUser, GoogleMessage
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.utils.connections import RedisMixin
from twisted.internet import defer
from twisted.python import log
import cyclone.web

class RequiredArgument(object):
    pass

class DefaultArgument(object):
    pass

class arguments(object):
    ARGUMENTS = {}
    PREFIX=''
    def __init__(self, handler):
        self.args = dict([(k,handler.get_argument(k)) if v is RequiredArgument else (k,handler.get_argument(k,v)) for k,v in self.ARGUMENTS.iteritems()])
        #Remove default arguments and add '_' prefix to keys
        self.args = dict([(self.PREFIX+k,v) for k,v in self.args.iteritems() if not v is DefaultArgument])

class login_arguments(arguments):
    PREFIX='_'
    ARGUMENTS = dict([('token', RequiredArgument), ('refreshtoken', RequiredArgument), ('resource', RequiredArgument),
                      ('pushtoken', ''), ('badgenumber', 0), ('pushsound',''), ('lang','en-US')])

class update_arguments(arguments):
    ARGUMENTS = dict([('token', DefaultArgument), ('refreshtoken', DefaultArgument), ('resource', DefaultArgument),
                      ('pushtoken', DefaultArgument), ('badgenumber', DefaultArgument), ('pushsound',DefaultArgument), ('lang', DefaultArgument)])

class MyRequestHandler(cyclone.web.RequestHandler, RedisMixin):
    def _response_json(self, value):
        self.set_header("Content-Type", "application/json")
        self.finish(json_encode(value))

class GoogleHandler(MyRequestHandler):
    @defer.inlineCallbacks
    def get(self, key):
        user = yield GoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        self._response_json(user.toDict())
    
    @defer.inlineCallbacks
    def post(self, key):
        args = login_arguments(self).args
        try:
            user = yield GoogleUser.load(key)
            if user is None or not user.connected:
                user = GoogleUser(_userid=key, **args)
                yield login(user)
                self._response_json({'success': True, 'reason': 'ok'})
            else:
                self._response_json({'success': False, 'reason': 'Already logged'})
        except XMPPUserAlreadyLogged:
            self._response_json({'success': False, 'reason': 'Already logged'})
    
    @defer.inlineCallbacks
    def put(self, key):
        args = update_arguments(self).args
        user = yield GoogleUser.load(key)
        if user is None or not user.connected:
            raise cyclone.web.HTTPError(404)
        try:
            yield update(key, **args)
            self._response_json({'success': True, 'reason': 'ok'})
        except XMPPUserNotLogged as e:
            raise cyclone.web.HTTPError(500, str(e))
    
    @defer.inlineCallbacks
    def delete(self, key):
        try:
            user = yield GoogleUser.load(key)
            if user is None:
                raise cyclone.web.HTTPError(404)
            if user.connected:
                yield logout(key)
            else:
                yield user.remove(user.userid)
            self._response_json({'success': True, 'reason': 'ok'})
        except XMPPUserNotLogged as e:
            #Remove user from database
            yield user.remove(user.userid)
            raise cyclone.web.HTTPError(500, str(e))

class GoogleMessagesHandler(MyRequestHandler):
    @defer.inlineCallbacks
    def get(self, key):
        user = yield GoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        messages = yield GoogleMessage.getMessages(key)
        self._response_json({'current_time': datetime.utcnow().isoformat()+'Z', 'success': True, 'messages': messages, 'len': len(messages), 'reason': 'ok'})
    
    @defer.inlineCallbacks
    def delete(self, key):
        user = yield GoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        #Remove messages from database (pending to implement)
        #update badgenumber
        try:
            yield GoogleMessage.flushMessages(key)
            if user.connected:
                yield update(key, **{'badgenumber': 0})
            self._response_json({'success': True, 'reason': 'ok'})
        except XMPPUserNotLogged as e:
            raise cyclone.web.HTTPError(500, str(e))
        

class AsyncHandler(MyRequestHandler):
    @cyclone.web.asynchronous
    def get(self, key):
        d = GoogleUser.load(key)
        d.addCallback(self._response_get)
        
    def _response_get(self, user):
        if user is None:
            self.send_error(404)
            return
        self._response_json(user.toDict())

class HelloHandler(MyRequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/plain")
        self.finish('Hello World')