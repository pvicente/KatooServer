from katoo import conf
from katoo.utils.connections import RedisMixin
import cyclone.bottle
import logging
import v1.handlers
from katoo.utils.applog import getLoggerAdapter, getLogger

log = getLogger(__name__)

class BaseHandler(cyclone.web.Application, RedisMixin):
    def __init__(self):
            handlers = [
                (r"/1/google/messages/(.+)", v1.handlers.GoogleMessagesHandler),
                (r"/1/google/contacts/(.+)", v1.handlers.GoogleContactsHandler),
                (r"/1/google/(.+)", v1.handlers.GoogleHandler)
            ]
            settings = dict(
                debug=conf.CYCLONE_DEBUG, 
            )
            cyclone.web.Application.__init__(self, handlers, **settings)
            self.log = getLoggerAdapter(log)
    
    def log_request(self, handler):
        request_time = 1000.0 * handler.request.request_time()
        getattr(handler, "log", self.log).info("%s %s %.2f(ms) User-Agent: %s Request: %s Response: %s", handler.get_status(), handler._request_summary(), request_time, 
                                               handler.request.headers.get('User-Agent',''), getattr(handler, 'args', ''), getattr(handler, 'response', ''))

class BaseHandlerNoLog(BaseHandler):
    def log_request(self, handler):
        pass


app = BaseHandler() if conf.LOG_REQUESTS else BaseHandlerNoLog()