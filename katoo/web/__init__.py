from katoo.utils.connections import RedisMixin
import v1.handlers
import cyclone.bottle

class BaseHandler(cyclone.web.Application, RedisMixin):
    def __init__(self):
            handlers = [
                (r"/1/google/messages/(.+)", v1.handlers.GoogleMessagesHandler),
                (r"/1/google/(.+)", v1.handlers.GoogleHandler)
            ]
            settings = dict(
                debug=True,
            )
            cyclone.web.Application.__init__(self, handlers, **settings)

app = BaseHandler()