'''
Created on Jun 4, 2013

@author: pvicente
'''
from twisted.python import log
class RequiredArgument(object):
    pass

class action(object):
    ARGUMENTS = {}
    def __init__(self, handler):
        self.args = dict([(k,handler.get_argument(k)) if v is RequiredArgument else (k,handler.get_argument(k,v)) for k,v in self.ARGUMENTS.iteritems()])
        self.handler = handler
    
class login(action):
    ARGUMENTS = {'token': RequiredArgument, 'refreshtoken': RequiredArgument, 'resource': RequiredArgument, 
                 'pushtoken': '','badgenumber' : 0, 'pushsound:': '', 'lang': 'en-US'}
    def __init__(self, appid, handler):
        super(login, self).__init__(handler)
        self.appid = appid
    
    def __call__(self):
        log.msg('performing login of %s with args: %s'%(self.appid, self.args))
        self.handler.finish('performed login')

