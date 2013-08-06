'''
Created on Aug 6, 2013

@author: pvicente
'''

from katoo import KatooApp
from katoo.utils.multiprocess import MultiProcess

application = KatooApp().app

m = MultiProcess('runxmpp.py')
m.setServiceParent(application)

