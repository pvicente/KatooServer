'''
Created on Jul 5, 2013

@author: pvicente
'''
from twisted.internet import defer, reactor

def sleep(secs):
    d = defer.Deferred()
    reactor.callLater(secs, d.callback, None)
    return d