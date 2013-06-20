'''
Created on May 25, 2013

@author: pvicente
'''
from functools import wraps
from katoo.utils.decorators import for_methods
from twisted.internet import reactor
from twisted.internet.tcp import Connection
from twisted.python import log
from twisted.words.protocols.jabber.sasl import SASLNoAcceptableMechanism, \
    get_mechanisms, SASLInitiatingInitializer, SASLAuthError
from twisted.words.protocols.jabber.sasl_mechanisms import ISASLMechanism
from twisted.words.xish import xmlstream
from wokkel.client import XMPPClient, XMPPClientConnector
from zope.interface import implements
import os
import time
import traceback

__all__ = ["ReauthXMPPClient"]

class ReauthXMPPClient(XMPPClient):
    AUTH_TIMEOUT=60
    
    def __init__(self, jid, password, host=None, port=5222):
        XMPPClient.__init__(self, jid, password, host=host, port=port)
        self.factory.addBootstrap(xmlstream.STREAM_ERROR_EVENT, self._onStreamError)
        self._authFailureTime = None
    
    def _onStreamError(self, reason):
        log.err(reason, 'STREAM_EROR_EVENT')
    
    def _authd(self, xs):
        self._authFailureTime = None
        XMPPClient._authd(self, xs)
    
    def isAuthenticating(self):
        return not self._authFailureTime is None
    
    def initializationFailed(self, reason):
        if not reason.check(SASLAuthError):
            return self.onAuthenticationError(reason)
        current_time = time.time()
        if self._authFailureTime is None:
            self._authFailureTime = current_time
            return self.onAuthenticationRenewal(reason)
        if current_time - self._authFailureTime > self.AUTH_TIMEOUT:
            return self.onAuthenticationError(reason)
    
    def onAuthenticationRenewal(self, reason):
        """
        Authentication failed: negotiate new authentication tokens with the server
        """
        #This method must be overrided and not called due to new reconnection will fail
        self._authFailureTime -= self.AUTH_TIMEOUT
    
    def onAuthenticationError(self, reason):
        """
        Authentication failed again after AUTH_TIMEOUT. Stopping the service disowning service
        with parent
        """
        #I cannot stop factory retrying and if I set the delay too higher, reconnection delay wil be executed in the future
        #and resetDelay will not work. Instead we wait 60 seconds to negotiate the new credentials
        log.err(reason, 'AUTH_ERROR_EVENT')
        
        #TODO: send a push notification to client and save disconnected state in client
        self.stopService()
        return self.disownServiceParent()
    
    def _getConnection(self):
        #By default pick domains from SRV with XMPPClientConnector
        c = XMPPClientConnector(reactor, self.domain, self.factory)
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

@for_methods(method_list=['setMechanism'], decorator=new_auth_methods)
class DecoratedSASLInitiatingInitializer(SASLInitiatingInitializer):
    """Injecting new_auth_methods decorator to setMechanism method"""
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
# @for_methods(method_list=['write', 'writeSequence'], decorator=log_writes)
# class MYConnection(Connection):
#     """Logging all writes of TCPTransport"""
#     pass
#===============================================================================

