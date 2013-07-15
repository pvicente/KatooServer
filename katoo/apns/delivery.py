'''
Created on Jun 11, 2013

@author: pvicente
'''
from katoo.txapns.txapns.encoding import encode_notifications
from katoo.txapns.txapns.payload import Payload, PayloadTooLargeError, \
    MAX_PAYLOAD_LENGTH

APNS = None

PADDING = "..."
LEN_PADDING = len(PADDING)

def sendapn(token, msg=None, sound=None, badgenumber=None, **kwargs):
    payload = None
    try:
        payload = Payload(alert=msg, sound=sound, badge=badgenumber, custom=kwargs)
    except PayloadTooLargeError as e:
        overload = MAX_PAYLOAD_LENGTH-(e.size+LEN_PADDING)
        msg = msg[:overload]+PADDING
        payload = Payload(alert=msg, sound=sound, badge=badgenumber, custom=kwargs)
    notification = encode_notifications(token, payload.dict())
    return APNS.write(notification)