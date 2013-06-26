'''
Created on Jun 4, 2013

@author: pvicente
'''

from cyclone.escape import json_encode
from datetime import datetime
from katoo.api import login, logout, update
from katoo.data import GoogleUser, GoogleMessage, GoogleContact
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
    ARGUMENTS = dict([('token', RequiredArgument), ('refreshtoken', RequiredArgument), ('resource', RequiredArgument), ('jid', RequiredArgument),
                      ('pushtoken', ''), ('badgenumber', 0), ('pushsound',''), ('lang','en-US')])

class update_arguments(arguments):
    ARGUMENTS = dict([('token', DefaultArgument), ('refreshtoken', DefaultArgument), ('resource', DefaultArgument),
                      ('pushtoken', DefaultArgument), ('badgenumber', DefaultArgument), ('pushsound',DefaultArgument), ('favoritesound', DefaultArgument), ('lang', DefaultArgument)])

class contact_arguments(arguments):
    ARGUMENTS = dict([('jid', RequiredArgument), ('name', None), ('favorite', DefaultArgument)])

class MyRequestHandler(cyclone.web.RequestHandler, RedisMixin):
    def __init__(self, application, request, **kwargs):
        cyclone.web.RequestHandler.__init__(self, application, request, **kwargs)
        self.key = ''
        self.args = ''
        self.response = ''
    
    def _response_json(self, value):
        self.set_header("Content-Type", "application/json")
        self.response = json_encode(value)
        self.finish(self.response)
        
    def constructor(self, key, args=''):
        self.key = key
        self.args = args

class GoogleHandler(MyRequestHandler):
    #===========================================================================
    # @defer.inlineCallbacks
    # def get(self, key):
    #     user = yield GoogleUser.load(key)
    #     if user is None:
    #         raise cyclone.web.HTTPError(404)
    #     self._response_json(user.toDict())
    #===========================================================================
    
    @defer.inlineCallbacks
    def get(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @defer.inlineCallbacks
    def post(self, key):
        self.constructor(key, login_arguments(self).args)
        try:
            user = yield GoogleUser.load(key)
            
            if user is None:
                #Logout of users with the same pushtoken
                user_to_logout = yield GoogleUser.load(pushtoken=self.args['_pushtoken'])
                if not user_to_logout is None:
                    log.msg('WEB_HANDLER_LOGOUT %s with the same pushtoken'%(user_to_logout.userid))
                    yield logout(user_to_logout.userid)
            elif user.connected:
                #Logout user with the same appid but other jid
                user_to_logout = yield GoogleUser.load(userid=key, jid=self.args['_jid'])
                if user_to_logout is None:
                    log.msg('WEB_HANDLER_LOGOUT %s with other jid: %s->%s'%(key, user.jid, self.args['_jid']))
                    yield logout(key)
                    user = None
            else:
                #user not connected removing from database
                yield user.remove(user.userid)
            
            if user is None or not user.connected:
                user = GoogleUser(_userid=key, **self.args)
                yield login(user)
                self._response_json({'success': True, 'reason': 'ok'})
            else:
                self._response_json({'success': False, 'reason': 'Already logged'})
        except XMPPUserAlreadyLogged:
            self._response_json({'success': False, 'reason': 'Already logged'})
    
    @defer.inlineCallbacks
    def put(self, key):
        self.constructor(key, update_arguments(self).args)
        user = yield GoogleUser.load(key)
        if user is None or not user.connected:
            raise cyclone.web.HTTPError(404)
        try:
            yield update(key, **self.args)
            self._response_json({'success': True, 'reason': 'ok'})
        except XMPPUserNotLogged as e:
            raise cyclone.web.HTTPError(500, str(e))
    
    @defer.inlineCallbacks
    def delete(self, key):
        self.constructor(key)
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
        self.constructor(key)
        user = yield GoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        messages = yield GoogleMessage.getMessages(key)
        self._response_json({'current_time': datetime.utcnow().isoformat()+'Z', 'success': True, 'messages': messages, 'len': len(messages), 'reason': 'ok', 'connected': user.connected})
    
    @defer.inlineCallbacks
    def delete(self, key):
        self.constructor(key)
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
    
class GoogleContactsHandler(MyRequestHandler):
    @defer.inlineCallbacks
    def get(self, key):
        self.constructor(key)
        contact = yield GoogleContact.exists(key)
        user = yield GoogleUser.load(key)
        if contact is None or user is None:
            raise cyclone.web.HTTPError(404)
        
        self._response_json({'success': True, 'reason': 'ok'})
    
    @defer.inlineCallbacks
    def put(self, key):
        self.constructor(key, contact_arguments(self).args)
        user = yield GoogleUser.load(key)
        if user is None or not user.connected:
            raise cyclone.web.HTTPError(404)
        
        jid = self.args.pop('jid')
        contact = yield GoogleContact.load(userid=key, jid=jid)
        if contact is None:
            contact = GoogleContact(_userid=key, _jid=jid)
        
        contact.update(**self.args)
        yield contact.save()
        self._response_json({'success': True, 'reason': 'ok'})
    
    @defer.inlineCallbacks
    def delete(self, key):
        self.constructor(key)
        user = yield GoogleUser.load(key)
        if user is None or not user.connected:
            raise cyclone.web.HTTPError(404)
        
        #Remove contacts from mongo
        yield GoogleContact.remove(user.userid)
        self._response_json({'success': True, 'reason': 'ok'})

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