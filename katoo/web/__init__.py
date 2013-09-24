from katoo import conf
from katoo.utils.connections import RedisMixin
import cyclone.bottle
import logging
import v1.handlers
from katoo.utils.applog import getLoggerAdapter, getLogger
from katoo.metrics import IncrementMetric, Metric

log = getLogger(__name__)

class BaseHandlerNoLog(cyclone.web.Application, RedisMixin):
    def __init__(self):
            handlers = [
                (r"/1/google/messages/(.+)", v1.handlers.GoogleMessagesHandler),
                (r"/1/google/contacts/(.+)", v1.handlers.GoogleContactsHandler),
                (r"/1/google/presence/(.+)", v1.handlers.GooglePresenceHandler),
                (r"/1/google/(.+)", v1.handlers.GoogleHandler)
            ]
            settings = dict(
                debug=conf.CYCLONE_DEBUG, 
            )
            cyclone.web.Application.__init__(self, handlers, **settings)
            self.log = getLoggerAdapter(log)
            self.metric = Metric(name='time', value=None, unit=v1.handlers.METRIC_UNIT_TIME, source=v1.handlers.METRIC_SOURCE, sampling=True)
            self.metric_response_codes={1: Metric(name='response_1XX', value=None, unit='requests', source=v1.handlers.METRIC_SOURCE),
                                        2: Metric(name='response_2XX', value=None, unit='requests', source=v1.handlers.METRIC_SOURCE),
                                        3: Metric(name='response_3XX', value=None, unit='requests', source=v1.handlers.METRIC_SOURCE),
                                        4: Metric(name='response_4XX', value=None, unit='requests', source=v1.handlers.METRIC_SOURCE),
                                        5: Metric(name='response_5XX', value=None, unit='requests', source=v1.handlers.METRIC_SOURCE)
                                        }
    
    @IncrementMetric(name='total', unit=v1.handlers.METRIC_UNIT, source=v1.handlers.METRIC_SOURCE)
    def log_request(self, handler):
        self._request_time = 1000 * handler.request.request_time()
        self.metric.add(self._request_time)
        
        status_metric = self.metric_response_codes.get(handler.get_status()/100, None)
        if not status_metric is None:
            status_metric.add(1)
        
        metric = getattr(handler, 'metric', None)
        if metric:
            metric.add(self._request_time)

class BaseHandler(BaseHandlerNoLog):
    def log_request(self, handler):
        BaseHandlerNoLog.log_request(self, handler)
        getattr(handler, "log", self.log).info("%s %s %.2f(ms) User-Agent: %s Request: %s Response: %s", handler.get_status(), handler._request_summary(), self._request_time, 
                                               handler.request.headers.get('User-Agent',''), getattr(handler, 'args', ''), getattr(handler, 'response', ''))


app = BaseHandler() if conf.LOG_REQUESTS else BaseHandlerNoLog()