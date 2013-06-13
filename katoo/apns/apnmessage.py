'''
Created on Oct 30, 2012

@author: pedro.vicente
'''

import re

emoji_online = u'\ue32b'
emoji_offline = u'\ue32c'

emojis={
            'online'     : u'\ue32e',
            'offline'    : u'\ue13c',
            'disconnect' : u'\ue252',
            'maxretries' : u'\ue252',
            'authfailed' : u'\ue252'
            }

custom_messages={
        'online':     {'en-US': u'went online'},
        'offline':    {'en-US': u'went offline'},
        'disconnect': {'en-US': u'Disconnected due to inactivity'},
        'maxretries' : {'en-US': u'Disconnected. Connection problem'},
        'authfailed' : {'en-US': u'Disconnected. Authentication error'}
}

class CustomMessageException(StandardError):
    def __init__(self, *args, **kwargs):
        StandardError.__init__(self, *args, **kwargs)

def get_custom_message(lang, type_msg):
    type_dict = custom_messages.get(type_msg)
    emoji = emojis.get(type_msg, '')
    if type_dict == None:
        raise CustomMessageException("%s doesn't exists on custom_messages" %(type_msg))
    return (emoji, type_dict.get(lang) or type_dict.get('en-US'))

class PushParser():
    '''Parse emoji/smileys of messages'''
    #emoji parser
    _emoji_string = u"\s+((\(((\^((\^((\^(\)))))))|(y(\)))))|(\-((\_(\-))))|(3((\:(\)|(\-(\)))))))|(\:((\'(\())|\(|\)|\*|(\-(\(|\)|\*|\/|D|O|P|\\|o|p))|\/|3|D|O|P|\[|\\|\]|o|p|(\|(\]))))|(\;(\)|(\-(\)))))|(\<((\(((\"(\)))))|3))|(\=(\(|\)|D|P))|(\>((\:(\(|(\-(\(|O|o))|O|o))))|(O((\.(o))|(\:(\)|(\-(\)))))))|(\^((\_(\^))))|(o((\.(O)))))\s+"
    _emoji_dict = {':/': u'\ue40e', ':(': u'\ue058', ':)': u'\ue415', ':*': u'\ue418', 'O.o': u'\ue108', '>:-O': u'\ue416', ':-D': u'\ue057', '3:)': u'\ue11a', ':-\\': u'\ue40e', ':-P': u'\ue409', ':-O': u'\ue40b', ':\\': u'\ue40e', '(^^^)': u'\ue019', ':-o': u'\ue40b', ':|]': u'\ue12b', '=)': u'\ue415', '>:(': u'\ue059', '>:-o': u'\ue416', 'O:)': u'\ue04e', '=D': u'\ue057', 'o.O': u'\ue108', ':-p': u'\ue409', ':3': u'\ue04f', ';-)': u'\ue405', ':o': u'\ue40b', '<3': u'\ue022', '>:O': u'\ue416', '<(")': u'\ue055', '^_^': u'\ue056', ':O': u'\ue40b', 'O:-)': u'\ue04e', ';)': u'\ue405', ':p': u'\ue409', '=(': u'\ue058', '=P': u'\ue409', ':-*': u'\ue418', '3:-)': u'\ue11a', ':-(': u'\ue058', ':-)': u'\ue415', ':-/': u'\ue40e', '-_-': u'\ue403', ':D': u'\ue057', '(y)': u'\ue00e', '>:-(': u'\ue059', '>:o': u'\ue416', ":'(": u'\ue413', ':]': u'\ue415', ':[': u'\ue058', ':P': u'\ue409'}
    #url parser
    _KATOO_URL = u'http://katooshare.herokuapp.com/'
    _KATOO_URL_LEN = len(_KATOO_URL)
    _MAPS_URL = u'http://maps.google.com/?q='
    _atachment_string = u'{0}p\S+|{0}v\S+|{0}a\S+|{1}\S+'.format(re.escape(_KATOO_URL), re.escape(_MAPS_URL))
    _atachment_dict = {_KATOO_URL+'p': u'\ue44a Image received', _KATOO_URL+'v': u'\ue324 Video received', _KATOO_URL+'a': u'\ue141 Audio received', _MAPS_URL: u'\ue130 Location received'}
    _regex_string = u'(' + _atachment_string + u'|' + _emoji_string + u')'
    #final regexp
    _regex_dict = dict(_emoji_dict.items()+_atachment_dict.items())
    _regex = re.compile(_regex_string)

    @classmethod
    def parse_message(cls, msg):
        offset = 0
        #adding whitespaces
        msg = ' ' + msg + ' '
        
        for smIterator in cls._regex.finditer(msg):
            oldLen = len(msg)
            
            key = smIterator.group(0)
            key_len = len(key)
            regex_key = key.strip()
            if key_len != len(regex_key):
                #it must be an emoji
                lwhitespaces = key.find(regex_key[0])
                rwhitespaces = key_len - key.rfind(regex_key[-1]) - lwhitespaces
                msg = msg[:(smIterator.start()+lwhitespaces-offset)]+cls._regex_dict[regex_key]+msg[smIterator.end()-rwhitespaces-offset:]
            else:
                #it must be an attachment
                if regex_key.find(cls._KATOO_URL) != -1:
                    regex_key = regex_key[:cls._KATOO_URL_LEN+1] #getting extra parameter p,v,a
                else:
                    regex_key = cls._MAPS_URL
                msg = u' {0} '.format(cls._regex_dict[regex_key]) #with whitespaces
            offset+= (oldLen-len(msg))
        
        #removing whitespaces
        return msg[1:-1]
    