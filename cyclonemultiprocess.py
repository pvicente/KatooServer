'''
Created on Jun 7, 2013

@author: pvicente
'''
import platform
installed_reactor = ''
if 'Linux-2.6' in platform.platform():
    from twisted.internet import epollreactor
    installed_reactor='EpollReactor'
    epollreactor.install()
else:
    from twisted.internet import selectreactor
    installed_reactor='SelectReactor'
    selectreactor.install()

from katoo import conf, KatooApp
from katoo.web import app
from os import environ
from socket import AF_INET
from sys import argv, executable
from twisted.python import log
import signal
import sys
from twisted.internet import reactor

def handler(signum, frame):
    reactor.stop()

signal.signal(signal.SIGTERM, handler)
signal.signal(signal.SIGINT, handler)

def main(fd=None):
    factory = app

    if fd is None:
        # Create a new listening port and several other processes to help out.                                                                     
        port = reactor.listenTCP(conf.PORT, factory)
        for i in range(3):
            reactor.spawnProcess(
                    None, executable, [executable, __file__, str(port.fileno())],
                childFDs={0: 0, 1: 1, 2: 2, port.fileno(): port.fileno()},
                env=environ)
    else:
        # Another process created the port, just start listening on it.                                                                            
        port = reactor.adoptStreamPort(fd, AF_INET, factory)
    log.startLogging(sys.stdout)
    log.msg('Installed', installed_reactor)
    reactor.run()


if __name__ == '__main__':
    if len(argv) == 1:
        main()
    else:
        main(int(argv[1]))