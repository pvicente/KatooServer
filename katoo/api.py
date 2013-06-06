'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import KatooApp
from katoo.exceptions import XMPPUserAlreadyLogged, XMPPUserNotLogged
from katoo.xmpp.xmppclient import XMPPGoogleClient
from twisted.internet import defer
from twisted.python import log

def login(xmppuser):
    log.msg('Logging of user:', xmppuser)
    userid = xmppuser.userid
    running_client = KatooApp().getService(userid)
    if not running_client is None:
        raise XMPPUserAlreadyLogged('Service %s already running'%(running_client))
    XMPPGoogleClient(xmppuser, KatooApp().app)
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
    d = defer.maybeDeferred(running_client.disownServiceParent)
    d.addCallback(lambda x: user.remove(userid))
    return d
    #remove user

if __name__ == '__main__':
    from twisted.internet import defer, reactor
    from katoo.data import XMPPGoogleUser
    import sys
    
    @defer.inlineCallbacks
    def example():
        user=XMPPGoogleUser(userid="1", token="asdasdf", refreshtoken="refreshtoken", resource="unknownresource", pushtoken="pushtoken", badgenumber="0", pushsound="asdfasdfas")
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