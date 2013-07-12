'''
Created on Jul 11, 2013

@author: pvicente
'''

from katoo import KatooApp, conf
from katoo.data import GoogleUser
from katoo.utils.applog import getLogger, getLoggerAdapter
from twisted.internet import defer
from xmppgoogle import XMPPGoogle

log = getLoggerAdapter(getLogger(__name__, level='INFO'), id='XMPP_KEEP_ALIVE-%s'%(conf.MACHINEID))

@defer.inlineCallbacks
def KeepAliveTask():
    print "running"
    db_connected_users = yield GoogleUser.get_connected(conf.MACHINEID)
    db_connected_users = [user.get('_userid') for user in db_connected_users]
    connected_users=[]
    
    for service in KatooApp():
        if isinstance(service, XMPPGoogle):
            connected_users.append(service.name)
            handler = getattr(service, 'handler', None)
            protocol = None if handler is None else getattr(handler, 'protocol', None)
            if protocol:
                try:
                    yield protocol.send(' ')
                except Exception as e:
                    log.warning('Exception launch %s', e)
    
    total_db_connected = len(db_connected_users)
    total_connected = len(connected_users)
    
    log.info('Connected: %s(DB) %s(WORKER)', total_db_connected, total_connected)
    
    if total_db_connected != total_connected:
        db_connected_users=set(db_connected_users)
        connected_users=set(connected_users)
        diff_db = db_connected_users.difference(connected_users)
        diff_worker= connected_users.difference(db_connected_users)
        log.warning('CROSS_CHECK_FAIL DB %r WORKER %r', diff_db, diff_worker)