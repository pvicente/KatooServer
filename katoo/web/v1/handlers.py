'''
Created on Jun 4, 2013

@author: pvicente
'''

from cyclone.escape import json_encode
from datetime import datetime
from katoo import conf
from katoo.api import API
from katoo.data import GoogleUser, GoogleMessage
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.utils.applog import getLoggerAdapter, getLogger
from katoo.utils.connections import RedisMixin
from twisted.internet import defer
import cyclone.web
import re
from katoo.metrics import IncrementMetric

log = getLogger(__name__)

METRIC_UNIT='requests'
METRIC_SOURCE='web'

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
                      ('pushtoken', ''), ('badgenumber', 0), ('pushsound',''), ('favoritesound', ''), ('lang','en-US')])

class update_arguments(arguments):
    ARGUMENTS = dict([('token', DefaultArgument), ('refreshtoken', DefaultArgument), ('resource', DefaultArgument),
                      ('pushtoken', DefaultArgument), ('badgenumber', DefaultArgument), ('pushsound',DefaultArgument), ('favoritesound', DefaultArgument), ('lang', DefaultArgument)])

class contact_arguments(arguments):
    ARGUMENTS = dict([('jid', RequiredArgument), ('contactName', DefaultArgument), ('favorite', DefaultArgument)])


class CheckUserAgent(object):
    RE = re.compile('^{0}\/(\d.\d.\d)'.format(conf.USER_AGENT))
    
    def __init__(self, user_agent):
        self._pass = True
        self._match = ""
        self._user_agent = user_agent
        if conf.USER_AGENT_CHECK:
            self._match = self.RE.findall(self._user_agent)
            print self._match
            if not self._match or not self._match[0][1] in conf.USER_AGENT_WL or self._match[0][1] in conf.USER_AGENT_BL:
                self._pass = False
    
    def __nonzero__(self):
        return self._pass
    
    def __str__(self):
        return self._user_agent

class MyRequestHandler(cyclone.web.RequestHandler, RedisMixin):
    
    def __init__(self, application, request, **kwargs):
        cyclone.web.RequestHandler.__init__(self, application, request, **kwargs)
        self.log = getLoggerAdapter(log)
        self.key = ''
        self.args = ''
        self.response = ''
    
    def _response_json(self, value):
        self.set_header("Content-Type", "application/json")
        self.response = json_encode(value)
        self.finish(self.response)
        
    def constructor(self, key, args_class=None):
        self.log = getLoggerAdapter(log, id=key)
        self.key = key
        self.args = '' if args_class is None else args_class(self).args
        agent = CheckUserAgent(self.request.headers.get('User-Agent', ''))
        if not bool(agent):
            raise cyclone.web.HTTPError(403)

class GoogleHandler(MyRequestHandler):
    
    @IncrementMetric(name='restapi_get_/google/*', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def get(self, key):
        self.constructor(key)
        user = yield GoogleUser.load(key)
        if user is None or not user.connected:
            raise cyclone.web.HTTPError(404)
        
        response_data = {'success': True, 'reason': 'ok', 'resource_connected': not user.away}
        self._response_json(response_data)
    
    @IncrementMetric(name='reatapi_post_/google/*', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def post(self, key):
        self.constructor(key, login_arguments)
        
        user = yield GoogleUser.load(key)
        user_to_logout = None
        
        if user is None:
            user_to_logout = yield GoogleUser.load(pushtoken=self.args['_pushtoken'])
        elif user.connected:
            user_to_logout = yield GoogleUser.load(userid=key, jid=self.args['_jid'])
        else:
            yield GoogleUser.remove(user.userid)
        
        if not user_to_logout is None:
            if user is None:
                self.log.info('WEB_HANDLER_LOGOUT %s with the same pushtoken',user_to_logout.userid)
            else:
                self.log.info('WEB_HANDLER_LOGOUT %s with other jid: %s->%s', key, user.jid, self.args['_jid'])
            
            if user_to_logout.connected:
                yield API(key, queue=user_to_logout.worker, synchronous_call=True).logout(user_to_logout.userid)
            else:
                yield GoogleUser.remove(user_to_logout.userid)
        
        try:
            response_data = {'success': False, 'reason': 'Already logged'}
            if user is None or not user.connected:
                user = GoogleUser(_userid=key, **self.args)
                yield API(key).login(user)
                response_data = {'success': True, 'reason': 'ok'}
        except XMPPUserAlreadyLogged:
            pass
        response_data.update(dict(background_time=conf.XMPP_BACKGROUND_TIME, resource_prefix=conf.XMPP_RESOURCE, gtalk_priority=conf.XMPP_GTALK_PRIORITY))
        self._response_json(response_data)
    
    @IncrementMetric(name='restapi_put_/google/*', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def put(self, key):
        self.constructor(key, update_arguments)
        user = yield GoogleUser.load(key)
        if user is None or not user.connected:
            raise cyclone.web.HTTPError(404)
        try:
            yield API(key, queue=user.worker).update(key, **self.args)
            self._response_json({'success': True, 'reason': 'ok', 'background_time': conf.XMPP_BACKGROUND_TIME, 'resource_prefix': conf.XMPP_RESOURCE, 'gtalk_priority': conf.XMPP_GTALK_PRIORITY})
        except XMPPUserNotLogged as e:
            raise cyclone.web.HTTPError(500, str(e))
    
    @IncrementMetric(name='restapi_delete_/google/*', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def delete(self, key):
        self.constructor(key)
        user = yield GoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        if user.connected:
            yield API(key, queue=user.worker).logout(key)
        else:
            yield user.remove(user.userid)
        self._response_json({'success': True, 'reason': 'ok'})

class GoogleMessagesHandler(MyRequestHandler):
    
    @IncrementMetric(name='restapi_get_/google/messages/*', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def get(self, key):
        self.constructor(key)
        user = yield GoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        messages = yield GoogleMessage.getMessages(key)
        self._response_json({'current_time': datetime.utcnow().isoformat()+'Z', 'success': True, 'messages': messages, 'len': len(messages), 'reason': 'ok', 'connected': user.connected})
    
    @defer.inlineCallbacks
    def post(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @defer.inlineCallbacks
    def put(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @IncrementMetric(name='restapi_delete_/google/messages/*', unit=METRIC_UNIT, source=METRIC_SOURCE)
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
                yield API(key, queue=user.worker).update(key, **{'badgenumber': 0})
            self._response_json({'success': True, 'reason': 'ok'})
        except XMPPUserNotLogged as e:
            raise cyclone.web.HTTPError(500, str(e))
    
class GoogleContactsHandler(MyRequestHandler):
    @defer.inlineCallbacks
    def get(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @defer.inlineCallbacks
    def post(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @IncrementMetric(name='restapi_put_/google/contacts/*', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def put(self, key):
        self.constructor(key, contact_arguments)
        user = yield GoogleUser.load(key)
        if user is None or not user.connected:
            raise cyclone.web.HTTPError(404)
        
        jid = self.args.pop('jid')
        try:
            yield API(key, queue=user.worker).update_contact(user.userid, jid, **self.args)
        except XMPPUserNotLogged as e:
            raise cyclone.web.HTTPError(500, str(e))
        self._response_json({'success': True, 'reason': 'ok'})
    
    @defer.inlineCallbacks
    def delete(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    