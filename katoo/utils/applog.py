'''
Created on Jun 28, 2013

@author: pvicente
'''
from patterns import Singleton
from twisted.python import log
import logging

DEFAULT_CONTEXT=dict(id='-')
DEFAULT_CONTEXT_FMT="[%(id)s]"


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
    
    @classmethod
    def getLoggerDefaultFormat(cls, fmt):
        return "%s %s %s"%(fmt, DEFAULT_CONTEXT_FMT, "%(message)s")
    
    def constructor(self, app, fmt, level):
        logging.basicConfig(format=self.getLoggerDefaultFormat(fmt), level=self.getLevelFromStr(level))
        log.PythonLoggingObserver.__init__(self,'katootwisted')
        self.logger = logging.LoggerAdapter(self.logger, DEFAULT_CONTEXT)
        app.setComponent(log.ILogObserver, self.emit)
        
    
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
    
    def getLogger(self, name):
        return logging.getLogger(name)

