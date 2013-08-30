'''
Created on Jun 11, 2013

@author: pvicente
'''

import re
from gettext import gettext as _
import translate
from katoo import conf

declare = _('image'), _('video'), _('location')

class PushParser():
    '''Parse emoji/smileys of messages'''
    #emoji parser
    _emoji_string = u"\s+((\-((\_(\-))))|(3((\:(\)|(\-(\)))))))|(\:((\'(\())|\(|\)|\*|(\-(\(|\)|\*|\/|D|O|P|\\|o|p))|\/|3|D|O|P|\[|\\|\]|o|p))|(\;(\)|(\-(\)))))|(\<(3))|(\=(\(|\)|D|P))|(\>((\:(\(|(\-(\(|O|o))|O|o))))|(O((\.(o))|(\:(\)|(\-(\)))))))|(\^((\_(\^))))|(o((\.(O)))))\s+"
    _emoji_dict = {':/': u'\ue40e', ':(': u'\ue058', ':)': u'\ue415', ':*': u'\ue418', 'O.o': u'\ue108', '>:-O': u'\ue416', ':-D': u'\ue057', '3:)': u'\ue11a', ':-\\': u'\ue40e', ':-P': u'\ue409', ':-O': u'\ue40b', ':\\': u'\ue40e', ':-o': u'\ue40b', '=)': u'\ue415', '>:(': u'\ue059', '>:-o': u'\ue416', 'O:)': u'\ue04e', '=D': u'\ue057', 'o.O': u'\ue108', ':-p': u'\ue409', ':3': u'\ue04f', ';-)': u'\ue405', ':o': u'\ue40b', '<3': u'\ue022', '>:O': u'\ue416', '^_^': u'\ue056', ':O': u'\ue40b', 'O:-)': u'\ue04e', ';)': u'\ue405', ':p': u'\ue409', '=(': u'\ue058', '=P': u'\ue409', ':-*': u'\ue418', '3:-)': u'\ue11a', ':-(': u'\ue058', ':-)': u'\ue415', ':-/': u'\ue40e', '-_-': u'\ue403', ':D': u'\ue057', '>:-(': u'\ue059', '>:o': u'\ue416', ":'(": u'\ue413', ':]': u'\ue415', ':[': u'\ue058', ':P': u'\ue409'}
    #url parser
    _KATOO_URL = u'http://share.katooapp.com/' if conf.PRODUCTION else u'http://katoosharedev.herokuapp.com/'
    _KATOO_URL_LEN = len(_KATOO_URL)
    _MAPS_URL = u'http://maps.google.com/?q='
    _atachment_string = u'{0}p\S+|{0}v\S+|{0}a\S+|{1}\S+'.format(re.escape(_KATOO_URL), re.escape(_MAPS_URL))
    _atachment_dict = {_KATOO_URL+'p': (u'\ue008', 'image'), _KATOO_URL+'v': (u'\ue12a', 'video'), _MAPS_URL: (u'\U0001f4cd', 'location')}
    _regex_string = u'(' + _atachment_string + u'|' + _emoji_string + u')'
    #final regexp
    _regex_dict = dict(_emoji_dict.items()+_atachment_dict.items())
    _regex = re.compile(_regex_string)

    @classmethod
    def parse_message(cls, msg, lang):
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
                emoji, string = cls._regex_dict[regex_key]
                msg = u' {0} {1} '.format(emoji, translate.TRANSLATORS[lang]._(string)) #with whitespaces
            offset+= (oldLen-len(msg))
        
        #removing whitespaces
        return msg[1:-1]
    