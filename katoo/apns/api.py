'''
Created on Jun 11, 2013

@author: pvicente
'''
from apnmessage import PushParser
from katoo import conf
from katoo.metrics import Metric, IncrementMetric
from katoo.system import DistributedAPI, AsynchronousCall
from katoo.txapns.txapns.apns import APNSService, APNSProtocol, \
    APNSClientFactory
from katoo.txapns.txapns.encoding import encode_notifications
from katoo.txapns.txapns.payload import Payload, PayloadTooLargeError, \
    MAX_PAYLOAD_LENGTH
from katoo.utils.decorators import inject_decorators
from katoo.utils.patterns import Singleton

METRIC_INCREMENT = 1 if conf.REDIS_WORKERS == 0 else 0.5
METRIC_UNIT = 'calls'
METRIC_SOURCE = 'APNS'

@inject_decorators(method_decorator_dict={'sendMessage': IncrementMetric(name='sendMessage', unit='calls', source=METRIC_SOURCE)})
class KatooAPNSProtocol(APNSProtocol):
    CONNECTIONS_METRIC=Metric(name='connections', value=None, unit='connections', source=METRIC_SOURCE, reset=False)
    
    @IncrementMetric(name='connectionMade', unit='calls', source=METRIC_SOURCE)
    def connectionMade(self):
        self.CONNECTIONS_METRIC.add(1)
        return APNSProtocol.connectionMade(self)
    
    @IncrementMetric(name='connectionLost', unit='calls', source=METRIC_SOURCE)
    def connectionLost(self, reason):
        self.CONNECTIONS_METRIC.add(-1)
        return APNSProtocol.connectionLost(self, reason)

class KatooAPNSClientFactory(APNSClientFactory):
    protocol=KatooAPNSProtocol

class KatooAPNSService(Singleton):
    def constructor(self):
        self.service = APNSService(cert_path=conf.APNS_CERT, environment=conf.APNS_SANDBOX, timeout=conf.APNS_TIMEOUT)
        self.service.clientProtocolFactory=KatooAPNSClientFactory
        self.service.setName(conf.APNSERVICE_NAME)

class API(DistributedAPI):
    PADDING = "..."
    LEN_PADDING = len(PADDING)
    
    def _sendapn(self, token, msg=None, sound=None, badgenumber=None, **kwargs):
        payload = None
        try:
            payload = Payload(alert=msg, sound=sound, badge=badgenumber, custom=kwargs)
        except PayloadTooLargeError as e:
            overload = MAX_PAYLOAD_LENGTH-(e.size+ self.LEN_PADDING)
            msg = msg[:overload]+self.PADDING
            payload = Payload(alert=msg, sound=sound, badge=badgenumber, custom=kwargs)
        notification = encode_notifications(token, payload.dict())
        return KatooAPNSService().service.write(notification)
    
    @Metric(name='sendchatmessage', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @AsynchronousCall(conf.DIST_QUEUE_PUSH)
    def sendchatmessage(self, msg, token, sound, badgenumber, jid, fullname, favorite):
        message = u'{0}{1}: {2}'.format(u'\ue32f' if favorite else '', fullname, PushParser.parse_message(msg))
        self.log.debug('SEND_CHAT_MESSAGE jid: %r fullname: %r badgenumber: %r sound: %r token: %r . %r. Raw msg: %r', jid, fullname, badgenumber, sound, token, message, msg)
        return self._sendapn(token=token , msg=message, sound=sound, badgenumber=badgenumber, jid=jid)
    
    @Metric(name='sendpush', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @AsynchronousCall(conf.DIST_QUEUE_PUSH)
    def sendpush(self, message, token, badgenumber, sound=''):
        self.log.debug('SEND_PUSH: %s token: %s, badgenumber: %s, sound: %s', message, token, badgenumber, sound)
        return self._sendapn(token, message, sound, badgenumber)
    

if __name__ == '__main__':
    import sys,os
    from twisted.internet import reactor
    from katoo import KatooApp
    import twisted.python.log
    
    twisted.python.log.startLogging(sys.stdout)
    app = KatooApp().app
    KatooAPNSService().service.setServiceParent(app)
    KatooApp().start()
    reactor.callLater(5, API().sendchatmessage, token=os.getenv('PUSHTOKEN', None), msg='esto es una prueba con txapns', sound='', badgenumber=1, jid='pedrovfer@gmail.com', fullname='Pedro')
    reactor.run()
