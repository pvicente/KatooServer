'''
Created on Jun 4, 2013

@author: pvicente
'''

from katoo.utils.connections import MongoMixin
from katoo.txMongoModel.mongomodel.model import Model

class XMPPGoogleUserModel(Model):
    def __init__(self):
        MongoMixin.setup()
        self.db=MongoMixin.mongo_db
        self.collection='xmppgoogleuser'
        Model.__init__(self, pool=MongoMixin.mongo_conn)

class XMPPGoogleUser(object):
    model = XMPPGoogleUserModel()
    
    def __init__(self, 
                 appid, 
                 token,
                 refreshtoken,
                 resource,
                 pushtoken = '',
                 badgenumber = "0",
                 pushsound = '',
                 lang= 'en-US'):
        self._appid = appid
        self._token = token
        self._refreshtoken = refreshtoken
        self._resource = resource
        self._pushtoken = pushtoken
        self._badgenumber = int(badgenumber)
        self._pushsound = pushtoken
        self._lang = lang
    
    def save(self):
        data=vars(self)
        return self.model.insert(**data)


if __name__ == '__main__':
    from twisted.internet import defer, reactor
    
    @defer.inlineCallbacks
    def example():
        user=XMPPGoogleUser(appid="1", token="accesstoken", refreshtoken="refreshtoken", resource="unknownresource", pushtoken="pushtoken", badgenumber="0", pushsound="asdfasdfas")
        yield user.save()
        
        
    reactor.callLater(1, example)
    reactor.callLater(2, reactor.stop)
    reactor.run()
    
    