'''
Created on Aug 29, 2013

@author: pvicente
'''
import os
from i18n.translator import Translator

class AppTranslators():
    ROOT = os.path.dirname(os.path.realpath(__file__))
    LANGUAGES = ['en', 'es']
    
    def __init__(self):
        self._default = Translator(self.ROOT, self.LANGUAGES, 'en')
        self._dict = dict([(lang, Translator(self.ROOT, self.LANGUAGES, lang)) for lang in self.LANGUAGES])
    
    def __getitem__(self, key):
        lang_key = key.split('-')
        if len(lang_key)==2:
            return self._default
        return self._dict.get(lang_key[0], self._default)
    
    def getDefault(self):
        return self._default

TRANSLATORS = AppTranslators()

if __name__ == '__main__':
    #Execute main with extract (get strings from code. Be careful not having venv in root) | compile (to get .mo files)
    import sys
    AppTranslators().getDefault().cmdline(sys.argv)