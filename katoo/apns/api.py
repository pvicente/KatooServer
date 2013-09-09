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
    
    def write(self, notification):
        return self.service.write(notification)

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
        return KatooAPNSService().write(notification)
    
    @Metric(name='sendchatmessage', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @AsynchronousCall(conf.DIST_QUEUE_PUSH)
    def sendchatmessage(self, msg, token, sound, badgenumber, jid, fullname, favorite, lang):
        message = u'{0}{1}: {2}'.format(u'\ue32f' if favorite else '', fullname, PushParser.parse_message(msg, lang))
        self.log.debug('SEND_CHAT_MESSAGE jid: %r fullname: %r badgenumber: %r sound: %r token: %r . %r. Raw msg: %r', jid, fullname, badgenumber, sound, token, message, msg)
        return self._sendapn(token=token , msg=message, sound=sound, badgenumber=badgenumber, jid=jid)
    
    @Metric(name='sendpush', value=METRIC_INCREMENT, unit=METRIC_UNIT, source=METRIC_SOURCE)
    @AsynchronousCall(conf.DIST_QUEUE_PUSH)
    def sendpush(self, message, token, badgenumber, sound=''):
        self.log.debug('SEND_PUSH: %s token: %s, badgenumber: %s, sound: %s', message, token, badgenumber, sound)
        return self._sendapn(token, message, sound, badgenumber)
    

if __name__ == '__main__':
    from twisted.internet import reactor, defer, task
    from katoo import KatooApp
    from katoo.utils.applog import getLoggerAdapter, getLogger
    from katoo.rqtwisted import worker
    import os,translate
    
    my_log = getLoggerAdapter(getLogger(__name__, level="DEBUG"), id='MYLOG')
    
    #@defer.inlineCallbacks
    def send():
        my_log.debug('Starting send')
        API('TEST').sendpush(message=translate.TRANSLATORS['en']._('disconnected'), token=os.getenv('PUSHTOKEN', None), badgenumber=0, sound='')
        my_log.debug('Finished send')
    
    @defer.inlineCallbacks
    def close():
        try:
            my_log.debug('Starting close')
            yield KatooAPNSService().service.factory.clientProtocol.transport.loseConnection()
        except Exception:
            pass
        finally:
            my_log.debug('Finished close')
    
    app = KatooApp().app
    KatooAPNSService().service.setServiceParent(app)
    KatooApp().start()
    
    import twisted.python.log
    twisted.python.log.startLoggingWithObserver(KatooApp().log.emit)
    t1 = task.LoopingCall(send)
    t1.start(2, now=False)
    t2= task.LoopingCall(close)
    t2.start(3, now=False)
    
    if conf.REDIS_WORKERS > 0:
        worker.LOGGING_OK_JOBS = conf.LOGGING_OK_JOBS
        w=worker.Worker([conf.MACHINEID, conf.DIST_QUEUE_LOGIN, conf.DIST_QUEUE_RELOGIN, conf.DIST_QUEUE_PUSH], name=conf.MACHINEID, loops=conf.REDIS_WORKERS, default_result_ttl=conf.DIST_DEFAULT_TTL, default_warmup=conf.TWISTED_WARMUP)
        w.log = getLoggerAdapter(getLogger('WORKER', level='INFO'), id='WORKER')
        w.setServiceParent(app)
    
    reactor.run()
