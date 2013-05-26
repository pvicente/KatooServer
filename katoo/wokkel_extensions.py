'''
Created on May 25, 2013

@author: pvicente
'''
from functools import wraps
from twisted.words.protocols.jabber.sasl import SASLNoAcceptableMechanism, \
    get_mechanisms, SASLInitiatingInitializer, SASLAuthError
from twisted.words.protocols.jabber.sasl_mechanisms import ISASLMechanism
from utils.decorators import for_methods
from wokkel.client import XMPPClient
from zope.interface import implements
import os

__all__ = ["ExtendedXMPPClient"]

class ExtendedXMPPClient(XMPPClient):
    def __init__(self, jid, password, host=None, port=5222):
        XMPPClient.__init__(self, jid, password, host=host, port=port)
    
    def initializationFailed(self, reason):
        try:
            XMPPClient.initializationFailed(self, reason)
        except SASLAuthError as e:
            self.onAuthError(e)
    
    def onAuthError(self, reason):
        raise NotImplemented()
    

class X_FACEBOOK_PLATFORM(object):
    '''
    Implements X_FACEBOOK_PLATFORM authentication: it is injected to SASLInitiatingInitializer class
    throught setMechanism method
    '''
    implements(ISASLMechanism)
    name = 'X-FACEBOOK-PLATFORM'
    api_key = os.getenv("APIKEY", "138055292887831")
    
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
        self.username=jid.full() 
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

