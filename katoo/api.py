'''
Created on Jun 5, 2013

@author: pvicente
'''
from katoo import KatooApp
from katoo.exceptions import XMPPUserAlreadyLogged
from katoo.xmpp.xmppclient import XMPPGoogleClient

def login(xmppuser):
    userid = xmppuser.userid
    running_service = KatooApp().getService(userid)
    if not running_service is None:
        raise XMPPUserAlreadyLogged('Service %s already running'%(running_service))
    XMPPGoogleClient(xmppuser, KatooApp().app)

def update(userid, **kwargs):
    pass

def logout(userid):
    pass


if __name__ == '__main__':
    from twisted.internet import defer, reactor
    from katoo.data import XMPPGoogleUser
    from twisted.python import log
    import sys
    
    @defer.inlineCallbacks
    def example():
        user=XMPPGoogleUser(userid="1", token="asdasdf", refreshtoken="refreshtoken", resource="unknownresource", pushtoken="pushtoken", badgenumber="0", pushsound="asdfasdfas")
        log.msg('User:%s before saving'%(user))
        res = yield user.save()
        log.msg('User %s: saved. Res %s'%(user, res))
        login(user)
        reactor.callLater(5, login, user)
    
    log.startLogging(sys.stdout)
    KatooApp().service.startService()
    reactor.callLater(1, example)
    reactor.run()