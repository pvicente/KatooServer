'''
Created on May 25, 2013

@author: pvicente
'''
from functools import wraps
from katoo.utils.applog import getLogger, getLoggerAdapter
from katoo.utils.decorators import inject_decorators
from katoo.utils.time import Timer
from twisted.internet import reactor, defer
from twisted.words.protocols.jabber import error
from twisted.words.protocols.jabber.sasl import SASLNoAcceptableMechanism, \
    get_mechanisms, SASLInitiatingInitializer, SASLAuthError
from twisted.words.protocols.jabber.sasl_mechanisms import ISASLMechanism
from twisted.words.xish import xmlstream
from wokkel.client import XMPPClient, XMPPClientConnector
from wokkel.xmppim import RosterClientProtocol, RosterRequest, RosterPushIgnored
from zope.interface import implements
import lxmldomishparser
import os
from datetime import timedelta

__all__ = ["ReauthXMPPClient"]

log = getLogger(__name__)

class ReauthXMPPClient(XMPPClient):
    AUTH_TIMEOUT=60
    
    def __init__(self, jid, password, host=None, port=5222, logid=None):
        XMPPClient.__init__(self, jid, password, host=host, port=port)
        self.log = getLoggerAdapter(log) if logid is None else getLoggerAdapter(log, id=logid)
        self.factory.addBootstrap(xmlstream.STREAM_ERROR_EVENT, self._onStreamError)
        self._authFailureTime = None
    
    def _onStreamError(self, reason):
        self.log.err(reason, 'STREAM_EROR_EVENT')
    
    def _connected(self, xs):
        XMPPClient._connected(self, xs)
        def logDataIn(buf):
            self.log.debug("RECV: %r", buf)

        def logDataOut(buf):
            self.log.debug("SEND: %r", buf)
        
        if self.logTraffic:
            self.xmlstream.rawDataInFn = logDataIn
            self.xmlstream.rawDataOutFn = logDataOut
    
    def _authd(self, xs):
        self._authFailureTime = None
        XMPPClient._authd(self, xs)
    
    def isAuthenticating(self):
        return not self._authFailureTime is None
    
    def initializationFailed(self, reason):
        if not reason.check(SASLAuthError):
            return self.onAuthenticationError(reason)
        current_time = Timer().utcnow()
        if self._authFailureTime is None:
            self._authFailureTime = current_time
            return self.onAuthenticationRenewal(reason)
        if (current_time - self._authFailureTime).seconds > self.AUTH_TIMEOUT:
            return self.onAuthenticationError(reason)
    
    def onAuthenticationRenewal(self, reason):
        """
        Authentication failed: negotiate new authentication tokens with the server
        """
        #This method must be overrided and not called due to new reconnection will fail
        if not self._authFailureTime is None:
            self._authFailureTime -= timedelta(seconds=self.AUTH_TIMEOUT)
    
    def onAuthenticationError(self, reason):
        """
        Authentication failed again after AUTH_TIMEOUT. Stopping the service disowning service
        with parent
        """
        #I cannot stop factory retrying and if I set the delay too higher, reconnection delay wil be executed in the future
        #and resetDelay will not work. Instead we wait 60 seconds to negotiate the new credentials
        self.log.err(reason, 'AUTH_ERROR_EVENT')
        
        self.stopService()
        return self.disownServiceParent()
    
    def _getConnection(self):
        #By default pick domains from SRV with XMPPClientConnector
        c = XMPPClientConnector(reactor, self.host, self.factory)
        c.connect()
        return c
    
class X_FACEBOOK_PLATFORM(object):
    '''
    Implements X_FACEBOOK_PLATFORM authentication: it is injected to SASLInitiatingInitializer class
    throught setMechanism method
    '''
    implements(ISASLMechanism)
    name = 'X-FACEBOOK-PLATFORM'
    api_key = os.getenv("FACEBOOK_APIKEY", "0")
    
    def __init__(self, jid, password):
        self.access_token = password
    
    def getInitialResponse(self):
        return None
    
    def getResponse(self, challenge=b''):
        if challenge:
            values = {}
            for kv in challenge.split(b'&'):
                key, value = kv.split(b'=')
                values[key] = value

            resp_data = {
                b'method': values[b'method'],
                b'v': b'1.0',
                b'call_id': b'1.0',
                b'nonce': values[b'nonce'],
                b'access_token': self.access_token,
                b'api_key': self.api_key
            }
            
            resp = '&'.join(['%s=%s' % (k, v) for k, v in resp_data.items()])
            return bytes(resp)
        return b''

class X_OAUTH2(object):
    '''
    Implements X_OAUTH2 authentication: it is injected to SASLInitiatingInitializer class
    throught setMechanism method
    '''
    implements(ISASLMechanism)
    name = 'X-OAUTH2'
    
    def __init__(self, jid, password):
        self.username=jid.userhost()
        self.access_token = password
    
    def getInitialResponse(self):
        return b'\x00' + self.username + b'\x00' + self.access_token
    
    def getResponse(self, challenge=b''):
        return challenge

def new_auth_methods(f):
    """A decorator to add new auth_methods to SASLInitiatingInitializer"""
    auth_methods = {X_FACEBOOK_PLATFORM.name : X_FACEBOOK_PLATFORM, X_OAUTH2.name : X_OAUTH2}
    method_names = set(auth_methods.keys())
        
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        res = None
        try:
            res = f(self, *args, **kwargs)
        except SASLNoAcceptableMechanism:
            pass
        finally:
            jid = self.xmlstream.authenticator.jid
            password = self.xmlstream.authenticator.password
            mechanisms = set(get_mechanisms(self.xmlstream))
            
            available_auth_methods = method_names.intersection(mechanisms)
            
            if jid.user is None or not available_auth_methods:
                raise SASLNoAcceptableMechanism()
            method = auth_methods[available_auth_methods.pop()]
            self.mechanism = method(jid, password)
            return res
    return wrapper

@inject_decorators(method_decorator_dict={'setMechanism' : new_auth_methods})
class DecoratedSASLInitiatingInitializer(SASLInitiatingInitializer):
    """Injecting new_auth_methods decorator to setMechanism method"""
    pass

def new_onRosterSet(f):
    log = getLoggerAdapter(getLogger('wokkel_onRosterSet', level='INFO'), id='TWISTED')
    
    @wraps(f)
    def wrapper(self, iq):
        def trapIgnored(failure):
            failure.trap(RosterPushIgnored)
            raise error.StanzaError('service-unavailable')

        request = RosterRequest.fromElement(iq)

        if (not self.allowAnySender and
                request.sender and
                request.sender.userhostJID() !=
                self.parent.jid.userhostJID()):
            d = defer.fail(RosterPushIgnored())
        elif request.item is None:
            log.info('_onRosterSet iq malformed. %s', iq.toXml())
            d = defer.fail(RosterPushIgnored())
        elif request.item.remove:
            d = defer.maybeDeferred(self.removeReceived, request)
        else:
            d = defer.maybeDeferred(self.setReceived, request)
        d.addErrback(trapIgnored)
        return d
    
    return wrapper

@inject_decorators(method_decorator_dict={'_onRosterSet': new_onRosterSet})
class MyRosterClientProtocol(RosterClientProtocol):
    pass

#===============================================================================
# def log_writes(f):
#     @wraps(f)
#     def wrapper(self, *args, **kwargs):
#         traceback.print_stack()
#         log.msg('log write object %s: *args: %s, **kwargs: %s'%(hex(id(self)), args, kwargs))
#         return f(self, *args, **kwargs)
#      
#     return wrapper
#  
# @inject_decorators(method_decorator_dict={'write': log_writes, 'writeSequence': log_writes})
# class MYConnection(Connection):
#     """Logging all writes of TCPTransport"""
#     pass
#===============================================================================

