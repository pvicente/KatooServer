'''
Created on Jun 5, 2013

@author: pvicente
'''

class XMPPUserAlreadyLogged(Exception):
    pass

class XMPPUserNotLogged(Exception):
    pass

class DistributedJobTimeout(Exception):
    pass

class DistributedJobFailure(Exception):
    pass