'''
Created on Jun 28, 2013

@author: pvicente
'''
import logging
from twisted.python import log
from patterns import Singleton

class TwistedLogging(Singleton, log.PythonLoggingObserver):
    
    @classmethod
    def getLevelFromStr(cls, level):
        """Return the logging level from level ('DEBUG', 'INFO', 'WARNING', 'CRITICAL', 'ERROR') or None if not valid"""
        try:
            ret = eval('logging.'+level)
            if not isinstance(ret, int):
                ret = None
        except Exception:
            ret = None
        finally:
            return ret
    
    def constructor(self):
        fmt="[%(levelname)s] [%(filename)s:%(funcName)s:%(lineno)d] %(message)s"
        level="DEBUG"
        logging.basicConfig(format=fmt, level=self.getLevelFromStr(level))
        log.PythonLoggingObserver.__init__(self,'katootwisted') 
        log.PythonLoggingObserver.start(self)
        
    def start(self):
        #Do nothing started in constructor
        pass
    
    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)
    
    def warn(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)


if __name__ == '__main__':
    from twisted.internet import reactor
    TwistedLogging()
    
    def test():
        log.msg('Hola q critical')
     
    reactor.callLater(1, test)
    reactor.run()
