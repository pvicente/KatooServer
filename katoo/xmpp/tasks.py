'''
Created on Jul 11, 2013

@author: pvicente
'''

from katoo import KatooApp
from katoo.utils.applog import getLogger, getLoggerAdapter
from twisted.internet import defer
from xmppgoogle import XMPPGoogle

log = getLoggerAdapter(getLogger(__name__, level='INFO'), id='XMPP_KEEP_ALIVE')

@defer.inlineCallbacks
def KeepAliveTask():
    for service in KatooApp():
        if isinstance(service, XMPPGoogle):
            handler = getattr(service, 'handler', None)
            protocol = None if handler is None else getattr(handler, 'protocol', None)
            if protocol:
                try:
                    yield protocol.send(' ')
                except Exception as e:
                    log.warning('Exception launch %s', e)
    