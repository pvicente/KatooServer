from katoo.utils.connections import RedisMixin
import v1.handlers
import cyclone.bottle

class BaseHandler(cyclone.web.Application, RedisMixin):
    def __init__(self):
            handlers = [
                (r"/1/google/(.+)", v1.handlers.GoogleHandler),
                (r"/1/google/messages/(.+)", v1.handlers.GoogleMessagesHandler)
            ]
            settings = dict(
                debug=True,
            )
            RedisMixin.setup()
            cyclone.web.Application.__init__(self, handlers, **settings)

app = BaseHandler()