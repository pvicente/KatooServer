import imaplib
import getpass
import atexit
from imapclient import imap_utf7

def find_messages(sock, label):
    mailbox = imap_utf7.encode(label)
    label = imap_utf7.encode(label.encode('utf-8'))
    try:
        # process regular mailbox
        sock.select(mailbox)
    except sock.error:
        pass
    else:
        resp, data = sock.uid('SEARCH', None, '(ALL)')
        assert resp == 'OK'
        for uid in data[0].split():
            # because we do select, this uid will be valid.
            yield uid
    try:
        # now process chats with that label
        sock.select("[Gmail]/Chats", True)
    except sock.error:
        # access to chats via IMAP is disabled most likely
        pass
    else:
        # resp, data = sock.uid('SEARCH', 'X-GM-RAW', 'label:%s' % label)
        sock.literal = label
        resp, data = sock.uid('SEARCH', 'CHARSET', 'UTF-8', 'X-GM-LABELS')
        assert resp == 'OK'
        for uid in data[0].split():
            # because we do select, this uid will be valid.
            yield uid

def test():
    email = "pedrovfer@gmail.com"
    label = u"chats" # oui oui merci beaucoup.
    sock = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    sock.login(email, getpass.getpass())
    for uid in find_messages(sock, label):
        # e.g.
        print sock.uid('FETCH', uid, '(BODY[HEADER])')
    sock.close()
    sock.logout()
