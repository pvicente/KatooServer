'''
Created on Jun 4, 2013

@author: pvicente
'''

from cyclone.escape import json_encode
from katoo import conf
from katoo.api import API
from katoo.data import GoogleUser, GoogleMessage
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.metrics import IncrementMetric, Metric
from katoo.utils.applog import getLoggerAdapter, getLogger
from katoo.utils.connections import RedisMixin
from katoo.utils.time import Timer
from twisted.internet import defer
import cyclone.web
import re

log = getLogger(__name__)

METRIC_UNIT='requests'
METRIC_UNIT_TIME='ms'
METRIC_SOURCE='RESTAPI'

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
    ARGUMENTS = dict([('jid', RequiredArgument), ('contactName', DefaultArgument), ('favorite', DefaultArgument), ('snoozePushTime', DefaultArgument)])

class presence_arguments(arguments):
    ARGUMENTS = dict([('jid', RequiredArgument), ('nextTimeAvailable', DefaultArgument)])

class CheckUserAgent(object):
    RE = re.compile('(\S+)\/(\S+)\s\((.+)\)'.format(conf.USER_AGENT))
    
    def _check_user_agent(self):
        self._match = self.RE.findall(self._user_agent)
        if self._match:
            self._agent, self._version, system = self._match[0]
            system = system.split(';')
            self._isApp = self._agent == conf.USER_AGENT
            if self._isApp:
                self._hwmodel, self._os = system[0], "" if len(system)==0 else system[1].strip()
            else:
                self._hwmodel = system[0]
        
        if conf.USER_AGENT_CHECK:
            if self._agent != conf.USER_AGENT or not self._version in conf.USER_AGENT_WL or self._version in conf.USER_AGENT_BL:
                self._pass = False
    
    def __init__(self, user_agent):
        self._pass = True
        self._user_agent = user_agent
        self._match = ""
        self._agent = ""
        self._version = conf.DEFAULT_VERSION
        self._hwmodel = conf.DEFAULT_VERSION
        self._os = ""
        self._isApp = False
        self._iosversion = conf.DEFAULT_VERSION
        self._check_user_agent()
    
    @property
    def isApp(self):
        return self._isApp
    
    @property
    def version(self):
        return self._version
    
    @property
    def hwmodel(self):
        return self._hwmodel
    
    @property
    def iosVersion(self):
        if self._iosversion == conf.DEFAULT_VERSION and self.isApp:
            ios = self._os.split()
            if ios[0] == 'iOS':
                self._iosversion = ios[-1]
        
        return self._iosversion
    
    def __nonzero__(self):
        return self._pass
    
    def __str__(self):
        return "agent: %s version: %s hw: %s os: %s"%(self._agent, self._version, self._hwmodel, self._os)

class MyRequestHandler(cyclone.web.RequestHandler, RedisMixin):
    METRICS={}
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
        
    def constructor(self, key, args_class=None, metric=None):
        self.log = getLoggerAdapter(log, id=key)
        self.metric = metric
        self.key = key
        self.args = '' if args_class is None else args_class(self).args
        self.user_agent = CheckUserAgent(self.request.headers.get('User-Agent', ''))
        if not bool(self.user_agent):
            raise cyclone.web.HTTPError(403)

class GoogleHandler(MyRequestHandler):
    METRICS={'get':    Metric(name='time_get_google', value=None, unit=METRIC_UNIT_TIME, source=METRIC_SOURCE, sampling=True),
             'post':   Metric(name='time_post_google', value=None, unit=METRIC_UNIT_TIME, source=METRIC_SOURCE, sampling=True),
             'put':    Metric(name='time_put_google', value=None, unit=METRIC_UNIT_TIME, source=METRIC_SOURCE, sampling=True),
             'delete': Metric(name='time_delete_google', value=None, unit=METRIC_UNIT_TIME, source=METRIC_SOURCE, sampling=True)
             }
    
    @IncrementMetric(name='get_google', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def get(self, key):
        self.constructor(key, metric=self.METRICS['get'])
        user = yield GoogleUser.load(key)
        if user is None or not user.connected:
            raise cyclone.web.HTTPError(404)
        
        response_data = {'success': True, 'reason': 'ok', 'resource_connected': not user.away}
        self._response_json(response_data)
    
    @IncrementMetric(name='post_google', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def post(self, key):
        self.constructor(key, login_arguments, metric=self.METRICS['post'])
        
        user = yield GoogleUser.load(key)
        user_to_logout = None
        
        pushtoken=self.args['_pushtoken']
        
        if user is None:
            if pushtoken:
                user_to_logout = yield GoogleUser.load(pushtoken=pushtoken)
        elif user.connected:
            if user.jid != self.args['_jid']:
                user_to_logout = user
        
        if not user_to_logout is None:
            if user is None:
                self.log.info('WEB_HANDLER_LOGOUT %s with the same pushtoken',user_to_logout.userid)
            else:
                self.log.info('WEB_HANDLER_LOGOUT %s with other jid: %s->%s', key, user.jid, self.args['_jid'])
            
            if user_to_logout.connected:
                yield API(key, queue=user_to_logout.worker, synchronous_call=True).logout(user_to_logout.userid)
            else:
                yield GoogleUser.remove(user_to_logout.userid)
            
            user = None
        
        try:
            response_data = {'success': False, 'reason': 'Already logged'}
            if user is None or not user.connected:
                user = GoogleUser(_userid=key, _version=self.user_agent.version, _iosversion = self.user_agent.iosVersion, _hwmodel= self.user_agent.hwmodel, 
                                  **self.args)
                yield API(key).login(user)
                response_data = {'success': True, 'reason': 'ok'}
        except XMPPUserAlreadyLogged:
            pass
        response_data.update(dict(background_time=conf.XMPP_BACKGROUND_TIME, resource_prefix=conf.XMPP_RESOURCE, gtalk_priority=conf.XMPP_GTALK_PRIORITY))
        self._response_json(response_data)
    
    @IncrementMetric(name='put_google', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def put(self, key):
        self.constructor(key, update_arguments, metric=self.METRICS['put'])
        user = yield GoogleUser.load(key)
        if user is None or not user.connected:
            raise cyclone.web.HTTPError(404)
        try:
            yield API(key, queue=user.worker).update(key, _version=self.user_agent.version, _iosversion = self.user_agent.iosVersion, _hwmodel= self.user_agent.hwmodel, 
                                                     **self.args)
            self._response_json({'success': True, 'reason': 'ok', 'background_time': conf.XMPP_BACKGROUND_TIME, 'resource_prefix': conf.XMPP_RESOURCE, 'gtalk_priority': conf.XMPP_GTALK_PRIORITY})
        except XMPPUserNotLogged as e:
            raise cyclone.web.HTTPError(500, str(e))
    
    @IncrementMetric(name='delete_google', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def delete(self, key):
        self.constructor(key, metric=self.METRICS['delete'])
        user = yield GoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        if user.connected:
            yield API(key, queue=user.worker).logout(key)
        else:
            yield user.remove(user.userid)
        self._response_json({'success': True, 'reason': 'ok'})

class GoogleMessagesHandler(MyRequestHandler):
    METRICS={'get':    Metric(name='time_get_google_messages', value=None, unit=METRIC_UNIT_TIME, source=METRIC_SOURCE, sampling=True),
             'delete': Metric(name='time_delete_google_messages', value=None, unit=METRIC_UNIT_TIME, source=METRIC_SOURCE, sampling=True)
             }
    
    @IncrementMetric(name='get_google_messages', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def get(self, key):
        self.constructor(key, metric=self.METRICS['get'])
        user = yield GoogleUser.load(key)
        if user is None:
            raise cyclone.web.HTTPError(404)
        messages = yield GoogleMessage.getMessages(key)
        self._response_json({'current_time': Timer().isoformat(), 'success': True, 'messages': messages, 'len': len(messages), 'reason': 'ok', 'connected': user.connected})
    
    @defer.inlineCallbacks
    def post(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @defer.inlineCallbacks
    def put(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @IncrementMetric(name='delete_google_messages', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def delete(self, key):
        self.constructor(key, metric=self.METRICS['delete'])
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
    METRICS={'put':    Metric(name='time_put_google_contacts', value=None, unit=METRIC_UNIT_TIME, source=METRIC_SOURCE, sampling=True)}
    
    @defer.inlineCallbacks
    def get(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @defer.inlineCallbacks
    def post(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @IncrementMetric(name='put_google_contacts', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def put(self, key):
        self.constructor(key, contact_arguments, metric=self.METRICS['put'])
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
    
class GooglePresenceHandler(MyRequestHandler):
    METRICS={'put':    Metric(name='time_put_google_presence', value=None, unit=METRIC_UNIT_TIME, source=METRIC_SOURCE, sampling=True)}
    
    @defer.inlineCallbacks
    def get(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @defer.inlineCallbacks
    def post(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
    
    @IncrementMetric(name='put_google_presence', unit=METRIC_UNIT, source=METRIC_SOURCE)
    @defer.inlineCallbacks
    def put(self, key):
        self.constructor(key, presence_arguments, metric=self.METRICS['put'])
        user = yield GoogleUser.load(key)
        if user is None or not user.connected:
            raise cyclone.web.HTTPError(404)
        
        jid = self.args.pop('jid')
        try:
            yield API(key, queue=user.worker).update_presence(user.userid, jid, **self.args)
        except XMPPUserNotLogged as e:
            raise cyclone.web.HTTPError(500, str(e))
        self._response_json({'success': True, 'reason': 'ok'})
    
    @defer.inlineCallbacks
    def delete(self, key):
        self.constructor(key)
        raise cyclone.web.HTTPError(404)
