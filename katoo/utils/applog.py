'''
Created on Jun 28, 2013

@author: pvicente
'''
from functools import wraps
from katoo.utils.decorators import for_methods
from patterns import Singleton
from twisted.python import log
import logging

DEFAULT_CONTEXT=dict(id='-')
DEFAULT_CONTEXT_FMT="[%(id)s]"

def add_context(f):
    @wraps(f)
    def wrapper(self, msg, kwargs):
        if not self.extra:
            self.extra=DEFAULT_CONTEXT
        return f(self, msg, kwargs)
    return wrapper

@for_methods(method_list=['process'], decorator=add_context)
class AppLoggingAdapter(logging.LoggerAdapter):
    def __init__(self, logger, extra):
        logging.LoggerAdapter.__init__(self, logger, extra)
        if not self.extra:
            self.extra.update(DEFAULT_CONTEXT)
    
    msg = logging.LoggerAdapter.info
    err = logging.LoggerAdapter.error

def getLogger(name):
    return logging.getLogger(name)
 
def getLoggerAdapter(logger, id=None):
    return AppLoggingAdapter(logger, dict(id=id))

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

if __name__ == '__main__':
    from twisted.application import service
    from twisted.internet import reactor
    from twisted.internet.task import LoopingCall
    import sys
    
    app_log = getLoggerAdapter(getLogger(__name__), id='kk')
    logging_log = logging.LoggerAdapter(logging.getLogger(__name__), {})
    
    def testing_logs():
        log.msg('Testing twisted log')
        logging_log.debug('Testing logging log')
        app_log.debug('Testing app log')
    
    app = service.Application('KatooApp')
    TwistedLogging(app, "", "DEBUG")
    log.startLogging(sys.stdout)
    l = LoopingCall(testing_logs)
    l.start(3, now=False)
    reactor.run()
    
    

