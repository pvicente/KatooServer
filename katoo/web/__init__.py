from katoo.utils.redis import RedisMixin
import v1
import cyclone.bottle

class BaseHandler(cyclone.web.Application, RedisMixin):
    def __init__(self):
            handlers = [
                (r"/1/google/(.+)", v1.GoogleHandler),
                (r"/1/google/messages/(.+)", v1.GoogleMessagesHandler)
            ]
            settings = dict(
                debug=True,
            )
            RedisMixin.setup()
            cyclone.web.Application.__init__(self, handlers, **settings)

app = BaseHandler()