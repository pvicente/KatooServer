'''
Created on Jun 11, 2013

@author: pvicente
'''

import regex
from gettext import gettext as _
import translate
from katoo import conf

declare = _('image'), _('video'), _('location'), _('sticker'), _('audio'), _('audio_sticker')

class PushParser():
    '''Parse emoji/smileys of messages'''
    #emoji parser
    _emoji_string = u"(\G|^|\s+)((\-((\_(\-))))|(3((\:(\)|(\-(\)))))))|(\:((\'(\())|\(|\)|\*|(\-(\(|\)|\*|\/|D|O|P|\\|o|p))|\/|3|D|O|P|\[|\\|\]|o|p))|(\;(\)|(\-(\)))))|(\<(3))|(\=(\(|\)|D|P))|(\>((\:(\(|(\-(\(|O|o))|O|o))))|(O((\.(o))|(\:(\)|(\-(\)))))))|(\^((\_(\^))))|(o((\.(O)))))($|\s+)"
    _emoji_dict = {':/': u'\ue40e', ':(': u'\ue058', ':)': u'\ue415', ':*': u'\ue418', 'O.o': u'\ue108', '>:-O': u'\ue416', ':-D': u'\ue057', '3:)': u'\ue11a', ':-\\': u'\ue40e', ':-P': u'\ue409', ':-O': u'\ue40b', ':\\': u'\ue40e', ':-o': u'\ue40b', '=)': u'\ue415', '>:(': u'\ue059', '>:-o': u'\ue416', 'O:)': u'\ue04e', '=D': u'\ue057', 'o.O': u'\ue108', ':-p': u'\ue409', ':3': u'\ue04f', ';-)': u'\ue405', ':o': u'\ue40b', '<3': u'\ue022', '>:O': u'\ue416', '^_^': u'\ue056', ':O': u'\ue40b', 'O:-)': u'\ue04e', ';)': u'\ue405', ':p': u'\ue409', '=(': u'\ue058', '=P': u'\ue409', ':-*': u'\ue418', '3:-)': u'\ue11a', ':-(': u'\ue058', ':-)': u'\ue415', ':-/': u'\ue40e', '-_-': u'\ue403', ':D': u'\ue057', '>:-(': u'\ue059', '>:o': u'\ue416', ":'(": u'\ue413', ':]': u'\ue415', ':[': u'\ue058', ':P': u'\ue409'}
    #url parser
    _KATOO_URL = u'http://share.katooapp.com/' if conf.PRODUCTION else u'http://katoosharedev.herokuapp.com/'
    _KATOO_URL_LEN = len(_KATOO_URL)
    _OLD_MAPS_URL = u'http://maps.google.com/?q='
    _MAPS_URL = u'https://maps.google.com/maps?q='
    _atachment_string = u'{0}p\S+|{0}v\S+|{0}a\S+|{0}s\S+|{1}\S+|{2}\S+'.format(regex.escape(_KATOO_URL), regex.escape(_OLD_MAPS_URL), regex.escape(_MAPS_URL))
    _atachment_dict = {_KATOO_URL+'p': (u'\ue008', 'image'), _KATOO_URL+'v': (u'\ue12a', 'video'), _KATOO_URL+'s':(u'', 'sticker'),
                       _KATOO_URL+'al':(u'\ue141', 'audio'), _KATOO_URL+'as':(u'\ue141','audio_sticker'), _MAPS_URL: (u'\U0001f4cd', 'location')}
    _regex_string = u'(' + _atachment_string + u'|' + _emoji_string + u')'
    #final regexp
    _regex_dict = dict(_emoji_dict.items()+_atachment_dict.items())
    _regex = regex.compile(_regex_string)

    @classmethod
    def parse_message(cls, msg, lang):
        offset = 0
        #adding whitespaces
        ret = []
        
        for smIterator in cls._regex.finditer(msg, concurrent=True):
            key = smIterator.group(1)
            regex_key = key.strip()
            if regex_key in cls._regex_dict:
                #it must be an emoji
                ret.append(msg[offset:smIterator.start()])
                ret.append(u' '.join([cls._regex_dict[regex_key] if v else v for v in key.split(u' ')]))
                offset=smIterator.end()
            else:
                #it must be an attachment
                if regex_key.find(cls._KATOO_URL) != -1:
                    extra_index = 2 if regex_key[cls._KATOO_URL_LEN+1]=='a' else 1
                    regex_key = regex_key[:cls._KATOO_URL_LEN+extra_index] #getting extra parameter p,v,s, al, as
                else:
                    regex_key = cls._MAPS_URL
                emoji, string = cls._regex_dict[regex_key]
                tstring = translate.TRANSLATORS[lang]._(string)
                msg = u'{0} {1}'.format(emoji, tstring) if emoji else tstring
        
        if ret:
            ret.append(msg[offset:])
            return u''.join(ret)
        else:
            return msg
    
if __name__ == '__main__':
    examples = [u'<3<3', u'<3 <3',u' <3 <3', u'<3 <3 ', u' <3 <3 ', u'asdfasdfasd <3 <3 asdfasdfasdfasdfasdf',u'http://katoosharedev.herokuapp.com/pimage1', u'http://katoosharedev.herokuapp.com/vvideo1', u'http://maps.google.com/?q=123123123']
    
    for i in examples:
        tmp = PushParser.parse_message(i, 'en')
        print i, len(i), tmp, len(tmp)
    