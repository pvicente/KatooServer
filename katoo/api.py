'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import KatooApp, conf
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.utils.applog import getLogger, getLoggerAdapter
from katoo.xmpp.xmppgoogle import XMPPGoogle

log = getLogger(__name__)

class API(object):
    def __init__(self, userid=None):
        self.userid = userid
        self.log = getLoggerAdapter(log, id=userid)

    def login(self, xmppuser):
        self.log.info('LOGIN %s. Data: %s', xmppuser.jid, xmppuser)
        userid = xmppuser.userid
        running_client = KatooApp().getService(userid)
        if not running_client is None:
            raise XMPPUserAlreadyLogged('Service %s already running'%(running_client))
        XMPPGoogle(xmppuser, KatooApp().app)
        xmppuser.worker=conf.MACHINEID
        return xmppuser.save()

    def update(self, userid, **kwargs):
        self.log.info('UPDATE. Data: %s', kwargs)
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        xmppuser = running_client.user
        xmppuser.update(**kwargs)
        return xmppuser.save()
    
    def logout(self, userid):
        self.log.info('LOGOUT')
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        user = running_client.user
        d = running_client.disconnect()
        d.addCallback(lambda x: user.remove(userid))
        return d
    
    def disconnect(self, userid, change_state=True):
        self.log.info('DISCONNECTING')
        running_client = KatooApp().getService(userid)
        if running_client is None:
            raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
        return running_client.disconnect(change_state)
    

if __name__ == '__main__':
    from twisted.internet import reactor, defer
    from katoo.data import GoogleUser
    
    my_log = getLoggerAdapter(getLogger(__name__))
    @defer.inlineCallbacks
    def example():
        user=GoogleUser(_userid="1", _token="asdasdf", _refreshtoken="refreshtoken", _resource="unknownresource", _pushtoken="pushtoken", _badgenumber="0", _pushsound="asdfasdfas", _jid='kk@gmail.com')
        my_log.info('User:%s before saving'%(user))
        res = yield user.save()
        my_log.info('User %s: saved. Res %s'%(user, res))
        API(user.userid).login(user)
        reactor.callLater(5, API(user.userid).login, user)
        reactor.callLater(7, API(user.userid).update, user.userid, token="ya29.AHES6ZRDTu4pDWdA_LBrNWF1vnI5NEtdB8V0v6JN46QTaw")
        reactor.callLater(10, API(user.userid).logout, user.userid)
        reactor.callLater(20, API(user.userid).login, user)
    
    #log.startLogging(sys.stdout)
    KatooApp().service.startService()
    reactor.callLater(1, example)
    import sys
    import twisted.python.log
    twisted.python.log.startLogging(sys.stdout)
    reactor.run()