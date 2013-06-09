from katoo import conf
from katoo.utils.connections import RedisMixin
from twisted.python import log
import cyclone.bottle
import v1.handlers

class BaseHandler(cyclone.web.Application, RedisMixin):
    def __init__(self):
            handlers = [
                (r"/1/google/messages/(.+)", v1.handlers.GoogleMessagesHandler),
                (r"/1/google/(.+)", v1.handlers.GoogleHandler),
                (r"/1/googleasync/(.+)", v1.handlers.AsyncHandler),
                (r"/", v1.handlers.HelloHandler)
            ]
            settings = dict(
                debug=conf.CYCLONE_DEBUG, 
            )
            cyclone.web.Application.__init__(self, handlers, **settings)
    
    def log_request(self, handler):
        request_time = 1000.0 * handler.request.request_time()
        log.msg("[" + handler.request.protocol + "] " +
                str(handler.get_status()) + " " + handler._request_summary() +
                " %.2fms" % request_time)


class BaseHandlerNoLog(BaseHandler):
    def log_request(self, handler):
        pass


app = BaseHandler() if conf.LOG_REQUESTS else BaseHandlerNoLog()