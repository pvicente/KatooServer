'''
Created on Jun 11, 2013

@author: pvicente
'''
from apnmessage import PushParser, get_custom_message, CustomMessageException
from katoo import conf
from katoo.system import DistributedAPI, AsynchronousCall
from katoo.txapns.txapns.apns import APNSService
from katoo.txapns.txapns.encoding import encode_notifications
from katoo.txapns.txapns.payload import Payload, PayloadTooLargeError, \
    MAX_PAYLOAD_LENGTH
from katoo.utils.patterns import Singleton

class KatooAPNSService(Singleton):
    def constructor(self):
        self.service = APNSService(cert_path=conf.APNS_CERT, environment=conf.APNS_SANDBOX, timeout=conf.APNS_TIMEOUT)
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
    
    @AsynchronousCall(conf.DIST_QUEUE_PUSH)
    def sendchatmessage(self, msg, token, sound, badgenumber, jid, fullname, emoji):
        message = u'{0}{1}: {2}'.format(emoji, fullname, PushParser.parse_message(msg))
        self.log.debug('SEND_CHAT_MESSAGE jid: %r fullname: %r badgenumber: %r sound: %r token: %r . %r. Raw msg: %r', jid, fullname, badgenumber, sound, token, message, msg)
        return self._sendapn(token=token , msg=message, sound=sound, badgenumber=badgenumber, jid=jid)
    
    @AsynchronousCall(conf.DIST_QUEUE_PUSH)
    def sendcustom(self, lang, token, badgenumber, type_msg, sound='', inter_msg=' ', **kwargs):
        '''send custom push notifications and kwargs are extra parameters in push_notification'''
        try:
            emoji,message = get_custom_message(lang = lang, type_msg = type_msg)
            message = u'{0}{1}{2}'.format(emoji, inter_msg, message)
            self.log.debug('SEND_CUSTOM_MESSAGE type: %r lang: %r badgenumber: %r sound: %r token: %r kwargs: %s. %r', type_msg, lang, badgenumber, sound, token, kwargs, message)
            return self._sendapn(msg = message, token=token, badgenumber=badgenumber, sound=sound, **kwargs)
        except CustomMessageException as e:
            self.log.err(e, 'APNS_GET_CUSTOM_MESSAGE')

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
