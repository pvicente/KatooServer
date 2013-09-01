'''
Created on Jun 28, 2013

@author: pvicente
'''
from functools import wraps
from katoo import conf
from katoo.utils.decorators import inject_decorators
from patterns import Singleton
from twisted.python import log, failure
import logging

DEFAULT_CONTEXT=dict(id='TWISTED')
DEFAULT_CONTEXT_FMT="[%(id)s]"

def add_context(f):
    @wraps(f)
    def wrapper(self, msg, kwargs):
        if not self.extra:
            self.extra=DEFAULT_CONTEXT
        return f(self, msg, kwargs)
    return wrapper

@inject_decorators(method_decorator_dict={'process': add_context})
class AppLoggingAdapter(logging.LoggerAdapter):
    def __init__(self, logger, extra):
        logging.LoggerAdapter.__init__(self, logger, extra)
        if not self.extra:
            self.extra.update(DEFAULT_CONTEXT)
    
    msg = logging.LoggerAdapter.info
    
    def err(self, _stuff=None, _why=None, **kw):
        msg = None
        if _stuff is None:
            error = failure.Failure()
        if not _why is None:
            msg = _why
        if isinstance(_stuff, failure.Failure):
            error = _stuff 
        elif not _stuff is None and isinstance(_stuff, Exception):
            error = failure.Failure(_stuff)
        else:
            error = None
            if msg is None:
                self.error("Error: %s", repr(_stuff))
            else:
                self.error("%s. Error: %s", msg, repr(_stuff))
        if not error is None:
            if msg is None:
                self.error("%s",error.getBriefTraceback())
            else:
                self.error("%s. %s", msg, error.getBriefTraceback())

def getLogger(name, level=None):
    ret = logging.getLogger(name)
    if not level is None:
        ret.setLevel(TwistedLogging.getLevelFromStr(level))
    return ret
 
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
    def getLoggerDefaultFormat(cls, extrafmt=None):
        if extrafmt is None:
            return "%s %s"%(conf.LOG_FORMAT, "%(message)s")
        else:
            return "%s %s %s"%(conf.LOG_FORMAT, extrafmt, "%(message)s")
    
    def constructor(self, app):
        logging.basicConfig(format=self.getLoggerDefaultFormat(DEFAULT_CONTEXT_FMT),
                            level=self.getLevelFromStr(conf.LOG_LEVEL))
        log.PythonLoggingObserver.__init__(self,'katootwisted')
        self.logger = AppLoggingAdapter(self.logger, {})
        app.setComponent(log.ILogObserver, self.emit)

if __name__ == '__main__':
    from twisted.application import service
    from twisted.internet import reactor, defer
    from twisted.internet.task import LoopingCall
    import sys
    
    app_log = getLoggerAdapter(getLogger(__name__), id='kk')
    logging_log = logging.LoggerAdapter(logging.getLogger(__name__), {})
    
    def raising_error():
        raise ValueError('Raising Error')
    
    def reporting_error():
        app_log.err(ValueError('Reporting Error'), 'Test why')
    
    def testing_logs():
        log.msg('Testing twisted log')
        logging_log.debug('Testing logging log')
        app_log.debug('Testing app log')
        
        d = defer.maybeDeferred(raising_error)
        d.addErrback(app_log.err)
        d = defer.maybeDeferred(reporting_error)
        d.addErrback(app_log.err)
    
    app = service.Application('KatooApp')
    TwistedLogging(app, "", "DEBUG")
    log.startLogging(sys.stdout)
    l = LoopingCall(testing_logs)
    l.start(3, now=False)
    reactor.run()

