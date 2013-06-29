from katoo import conf
from katoo.utils.connections import RedisMixin
import cyclone.bottle
import katoo
import v1.handlers

log = katoo.getLogger(__name__)

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
    
    def log_request(self, handler):
        request_time = 1000.0 * handler.request.request_time()
        log.info("[cyclone %s] %s %s %.2f(ms) %s %s", getattr(handler, 'key', '-'), handler.get_status(), handler._request_summary(), request_time, getattr(handler, 'args', ''), getattr(handler, 'response', ''))

class BaseHandlerNoLog(BaseHandler):
    def log_request(self, handler):
        pass


app = BaseHandler() if conf.LOG_REQUESTS else BaseHandlerNoLog()