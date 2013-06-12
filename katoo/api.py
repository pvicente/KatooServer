'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import KatooApp
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.xmpp.xmppgoogle import XMPPGoogle
from twisted.python import log

def login(xmppuser):
    log.msg('Logging of user:', xmppuser)
    userid = xmppuser.userid
    running_client = KatooApp().getService(userid)
    if not running_client is None:
        raise XMPPUserAlreadyLogged('Service %s already running'%(running_client))
    XMPPGoogle(xmppuser, KatooApp().app)
    return xmppuser.save()

def update(userid, **kwargs):
    log.msg('updating user: %s with kwargs:%s'%(userid, kwargs))
    running_client = KatooApp().getService(userid)
    if running_client is None:
        raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
    xmppuser = running_client.user
    xmppuser.update(**kwargs)
    return xmppuser.save()

def logout(userid):
    log.msg('logout of user:', userid)
    running_client = KatooApp().getService(userid)
    if running_client is None:
        raise XMPPUserNotLogged('User %s is not running in current worker'%(userid))
    user = running_client.user
    d = running_client.disconnect()
    d.addCallback(lambda x: user.remove(userid))
    return d

if __name__ == '__main__':
    from twisted.internet import reactor, defer
    from katoo.data import GoogleUser
    import sys
    
    @defer.inlineCallbacks
    def example():
        user=GoogleUser(_userid="1", _token="asdasdf", _refreshtoken="refreshtoken", _resource="unknownresource", _pushtoken="pushtoken", _badgenumber="0", _pushsound="asdfasdfas", _jid='kk@gmail.com')
        log.msg('User:%s before saving'%(user))
        res = yield user.save()
        log.msg('User %s: saved. Res %s'%(user, res))
        login(user)
        reactor.callLater(5, login, user)
        reactor.callLater(7, update, user.userid, token="ya29.AHES6ZRDTu4pDWdA_LBrNWF1vnI5NEtdB8V0v6JN46QTaw")
        reactor.callLater(10, logout, user.userid)
        reactor.callLater(20, login, user)
    
    log.startLogging(sys.stdout)
    KatooApp().service.startService()
    reactor.callLater(1, example)
    reactor.run()