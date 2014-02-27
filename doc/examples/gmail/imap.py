#!/usr/bin/python
"""
Connect to an IMAP4 server with Twisted.
---------------------------------------
Run like so:
    $ python twisted_imap4_example.py

This example is slightly Gmail specific,
in that SSL is required, and the correct
server name and ports are set for Gmail.

This solution originally by Phil Mayers, on twisted-python:
http://twistedmatrix.com/pipermail/twisted-python/2009-June/019793.html
"""

from twisted.internet import reactor, protocol, defer
from twisted.mail import imap4
from twisted.internet import ssl

defer.Deferred.debug = True

USERNAME = 'pedrovfer@gmail.com'
PASSWORD = 'PyL070407_'

# Gmail specific:
SERVER = 'imap.gmail.com'
PORT = 993
# Gmail requires you connect via SSL, so
#we pass the follow object to 'someclient.connectSSL':
contextFactory = ssl.ClientContextFactory()

def mailboxes(list):
    print list
    for flags,sep,mbox in list:
        print mbox

@defer.inlineCallbacks
def loggedin(res, proto):
    list = yield proto.list('','*')
    yield mailboxes(list)
    yield proto.examine("[Gmail]/Chats")
    query = imap4.Query(all=True, uid='4900:*')
    print query
    ret = yield proto.search(query)
    print ret
    for msgid in ret:
        ret = yield proto.fetchFull(msgid)
        print ret
        ret = yield proto.fetchBody(msgid)
        print ret




def connected(proto):
    print "connected", proto
    d = proto.login(USERNAME, PASSWORD)
    d.addCallback(loggedin, proto)
    d.addErrback(failed)
    return d

def failed(f):
    print "failed", f
    return f

def done(_):
    reactor.callLater(0, reactor.stop)

def main():
    c = protocol.ClientCreator(reactor, imap4.IMAP4Client)
    d = c.connectSSL(SERVER, PORT, contextFactory)
    d.addCallbacks(connected, failed)
    d.addBoth(done)

reactor.callLater(0, main)
reactor.run()

