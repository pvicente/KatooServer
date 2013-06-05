'''
Created on Jun 4, 2013

@author: pvicente
'''

from katoo.txMongoModel.mongomodel.model import Model
from katoo.utils.connections import MongoMixin
from txmongo._pymongo.objectid import ObjectId

class ModelMixin(Model, MongoMixin):
    def __init__(self, collectionName, url=None):
        self.setup(url)
        self.db = self.mongo_db
        self.collection = collectionName
        Model.__init__(self, pool=self.mongo_conn)
    
class XMPPGoogleUserModel(ModelMixin):
        pass

class XMPPGoogleUser(object):
    model = XMPPGoogleUserModel('xmppgoogleuser')
    
    @classmethod
    def load(cls, userid):
        d = cls.model.find_one({'userid': userid})
        d.addCallback(lambda result: None if not result else cls(**result))
        return d
    
    def __init__(self,
                 userid, 
                 token,
                 refreshtoken,
                 resource,
                 pushtoken = '',
                 badgenumber = "0",
                 pushsound = '',
                 lang= 'en-US',
                 _id = None):
        self.userid = unicode(userid)
        self.token = unicode(token)
        self.refreshtoken = unicode(refreshtoken)
        self.resource = unicode(resource)
        self.pushtoken = unicode(pushtoken)
        self.badgenumber = int(badgenumber)
        self.pushsound = unicode(pushsound)
        self.lang = unicode(lang)
        if isinstance(_id, ObjectId):
            self._id = _id
    
    def save(self):
        data=vars(self)
        return self.model.insert(**data)
    
    def __str__(self):
        return '<%s object at %s>(%s)'%(self.__class__.__name__, hex(id(self)), vars(self))
    
    def __repr__(self):
        return '<%s object at %s (_id:%s, appid:%s)>'%(self.__class__.__name__, hex(id(self)), getattr(self, '_id', None), self.userid)
    


if __name__ == '__main__':
    from twisted.internet import defer, reactor
    
    @defer.inlineCallbacks
    def example():
        user=XMPPGoogleUser(userid="1", token="accesstoken", refreshtoken="refreshtoken", resource="unknownresource", pushtoken="pushtoken", badgenumber="0", pushsound="asdfasdfas")
        yield user.save()
        data = yield user.model.find_one({'appid' : "1"})
        print data
        data2 = yield user.model.find_one({'appid' : "2"})
        print data2
        
        user2 = yield XMPPGoogleUser.load("1")
        print user2
        
        user3 = yield XMPPGoogleUser.load("2")
        print user3
        
    reactor.callLater(1, example)
    reactor.callLater(2, reactor.stop)
    reactor.run()
    
    