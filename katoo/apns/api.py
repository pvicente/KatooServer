'''
Created on Aug 1, 2012

@author: pedro.vicente
'''
from apnmessage import PushParser, get_custom_message, CustomMessageException
from delivery import sendapn
from twisted.python import log

def sendchatmessage(msg, token, sound, badgenumber, jid, fullname):
    message = PushParser.parse_message(msg)
    return sendapn(token=token , msg=u'{0}: {1}'.format(fullname, message), sound=sound, badgenumber=badgenumber, jid=jid)
    
def sendcustom(lang, token, badgenumber, type_msg, sound='', inter_msg=' ', **kwargs):
    '''send custom push notifications and kwargs are extra parameters in push_notification'''
    try:
        emoji,message = get_custom_message(lang = lang, type_msg = type_msg)
        message = u'{0}{1}{2}'.format(emoji, inter_msg, message)
        return sendapn(msg = message, token=token, badgenumber=badgenumber, sound=sound, **kwargs)
    except CustomMessageException as e:
        log.err('APNS_GET_CUSTOM_MESSAGE: %s'%(e.message))

if __name__ == '__main__':
    import sys,os
    from twisted.internet import reactor
    from katoo import KatooApp
    from katoo.txapns.txapns.apns import APNSService
    from katoo import conf
    import delivery
    
    delivery.ApnService = apns = APNSService(cert_path=conf.APNS_CERT, environment=conf.APNS_SANDBOX, timeout=5)
    apns.setName(conf.APNSERVICE_NAME)
    log.startLogging(sys.stdout)
    app = KatooApp().app
    apns.setServiceParent(app)
    KatooApp().start()
    reactor.callLater(5, sendchatmessage, token=os.getenv('PUSHTOKEN', None), msg='esto es una prueba con txapns', sound='', badgenumber=1, jid='pedrovfer@gmail.com', fullname='Pedro')
    reactor.run()
