'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import KatooApp, conf
from katoo.system import DistributedAPI, SynchronousCall
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.utils.applog import getLogger, getLoggerAdapter
from katoo.xmpp.xmppgoogle import XMPPGoogle

log = getLogger(__name__)

class API(DistributedAPI):
    def __init__(self, userid=None, queue=None):
        DistributedAPI.__init__(self, queue)
        self.userid = userid
        self._log = getLoggerAdapter(log, id=self.userid)
    
    def __getstate__(self):
        self._log = None
        return self.__dict__
    
    @property
    def log(self):
        if self._log is None:
            self._log = getLoggerAdapter(log, id=self.userid)
        return self._log
    
    @SynchronousCall(queue=conf.DIST_QUEUE_LOGIN)
    def login(self, xmppuser):
        self.log.info('LOGIN %s. Data: %s', xmppuser.jid, xmppuser)
        userid = xmppuser.userid
        running_client = KatooApp().getService(userid)
        if not running_client is None:
            raise XMPPUserAlreadyLogged('Service %s already running'%(running_client))
        XMPPGoogle(xmppuser, KatooApp().app)
        xmppuser.worker=conf.MACHINEID
        return xmppuser.save()
    
    @SynchronousCall(queue=None) #Queue is assigned at run time
    def update(self, userid, **kwargs):
        self.log.info('UPDATE. Data: %s', kwargs)
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        xmppuser = running_client.user
        xmppuser.update(**kwargs)
        return xmppuser.save()
    
    @SynchronousCall(queue=None) #Queue is assigned at run time
    def logout(self, userid):
        self.log.info('LOGOUT')
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        user = running_client.user
        d = running_client.disconnect()
        d.addCallback(lambda x: user.remove(userid))
        return d
    
    @SynchronousCall(queue=None) #Queue is assigned at run time
    def disconnect(self, userid, change_state=True):
        self.log.info('DISCONNECTING')
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        return running_client.disconnect(change_state)
    
    