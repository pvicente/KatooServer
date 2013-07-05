'''
Created on Jun 11, 2013

@author: pvicente
'''
from apnmessage import PushParser, get_custom_message, CustomMessageException
from delivery import sendapn
from katoo import conf
from katoo.system import DistributedAPI, AsynchronousCall

class API(DistributedAPI):
    
    @AsynchronousCall(conf.DIST_QUEUE_PUSH)
    def sendchatmessage(self, msg, token, sound, badgenumber, jid, fullname, emoji):
        message = u'{0}{1}: {2}'.format(emoji, fullname, PushParser.parse_message(msg))
        self.log.debug('SEND_CHAT_MESSAGE jid: %r fullname: %r badgenumber: %r sound: %r token: %r . %r. Raw msg: %r', jid, fullname, badgenumber, sound, token, message, msg)
        return sendapn(token=token , msg=message, sound=sound, badgenumber=badgenumber, jid=jid)
    
    @AsynchronousCall(conf.DIST_QUEUE_PUSH)
    def sendcustom(self, lang, token, badgenumber, type_msg, sound='', inter_msg=' ', **kwargs):
        '''send custom push notifications and kwargs are extra parameters in push_notification'''
        try:
            emoji,message = get_custom_message(lang = lang, type_msg = type_msg)
            message = u'{0}{1}{2}'.format(emoji, inter_msg, message)
            self.log.debug('SEND_CUSTOM_MESSAGE type: %r lang: %r badgenumber: %r sound: %r token: %r kwargs: %s. %r', type_msg, lang, badgenumber, sound, token, kwargs, message)
            return sendapn(msg = message, token=token, badgenumber=badgenumber, sound=sound, **kwargs)
        except CustomMessageException as e:
            self.log.err(e, 'APNS_GET_CUSTOM_MESSAGE')

if __name__ == '__main__':
    import sys,os
    from twisted.internet import reactor
    from katoo import KatooApp
    from katoo.txapns.txapns.apns import APNSService
    import twisted.python.log
    import delivery
    
    delivery.ApnService = apns = APNSService(cert_path=conf.APNS_CERT, environment=conf.APNS_SANDBOX, timeout=5)
    apns.setName(conf.APNSERVICE_NAME)
    twisted.python.log.startLogging(sys.stdout)
    app = KatooApp().app
    apns.setServiceParent(app)
    KatooApp().start()
    reactor.callLater(5, API().sendchatmessage, token=os.getenv('PUSHTOKEN', None), msg='esto es una prueba con txapns', sound='', badgenumber=1, jid='pedrovfer@gmail.com', fullname='Pedro')
    reactor.run()
