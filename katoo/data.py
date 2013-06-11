'''
Created on Jun 4, 2013

@author: pvicente
'''

from katoo.txMongoModel.mongomodel.model import Model
from katoo.utils.connections import MongoMixin
from txmongo._pymongo.objectid import ObjectId
from datetime import datetime

class ModelMixin(Model, MongoMixin):
    def __init__(self, collectionName, mongourl=None):
        self.setup(url=mongourl)
        self.db = self.mongo_db
        self.collection = collectionName
        Model.__init__(self, pool=self.mongo_conn)
    
class DataModel(ModelMixin):
    def __init__(self, collectionName, mongourl=None):
        ModelMixin.__init__(self, collectionName, mongourl=mongourl)

class GoogleMessage(object):
    model = DataModel(collectionName='googlemessages')
    
    @classmethod
    def getMessages(cls, userid):
        return cls.model.find(spec={'userid':userid}, fields={'_id':0, 'time':1, 'fromid':1, 'msgid':1, 'data':1})
    
    @classmethod
    def flushMessages(cls, userid):
        return cls.model.remove({'userid':userid})
    
    def __init__(self, userid, fromid, msgid, data):
        self.userid = userid
        self.fromid = fromid
        self.msgid = msgid
        self.data = data
        self.time = datetime.utcnow().isoformat()+'Z'
    
    def save(self):
        data=vars(self)
        return self.model.insert(**data)
    

class GoogleUser(object):
    model = DataModel(collectionName='googleusers')
    
    @classmethod
    def load(cls, userid):
        d = cls.model.find_one({'_userid': userid})
        d.addCallback(lambda result: None if not result else cls(**result))
        return d
    
    @classmethod
    def remove(cls, userid):
        d = cls.model.remove({'_userid':userid})
        d.addCallback(GoogleMessage.flushMessages(userid))
        return d
    
    def __init__(self,
                 _userid, 
                 _token,
                 _refreshtoken,
                 _resource,
                 _pushtoken = '',
                 _badgenumber = 0,
                 _pushsound = '',
                 _lang= 'en-US',
                 _connected=True,
                 _id = None):
        self._userid = unicode(_userid)
        self._token = unicode(_token)
        self._refreshtoken = unicode(_refreshtoken)
        self._resource = unicode(_resource)
        self._pushtoken = unicode(_pushtoken)
        self._badgenumber = int(_badgenumber)
        self._pushsound = unicode(_pushsound)
        self._lang = unicode(_lang)
        self._connected = eval(str(_connected))
        if isinstance(_id, ObjectId):
            self._id = _id
    
    def save(self):
        data=vars(self)
        return self.model.update({'_userid': self.userid}, upsert=True, multi=False, **data)
    
    def update(self, **kwargs):
        for k,v in kwargs.iteritems():
            setattr(self,k,v);
    
    def toDict(self):
        ret = dict(vars(self))
        _id = ret.get('_id')
        if not _id is None:
            ret['_id'] = str(_id)
        return ret
    
    def __str__(self):
        return '<%s object at %s>(%s)'%(self.__class__.__name__, hex(id(self)), vars(self))
    
    def __repr__(self):
        return '<%s object at %s (_id:%s, appid:%s)>'%(self.__class__.__name__, hex(id(self)), getattr(self, '_id', None), self.userid)
    
    @property
    def userid(self):
        return self._userid
    
    @property
    def token(self):
        return self._token
    
    @token.setter
    def token(self, value):
        self._token = unicode(value)
    
    @property
    def refreshtoken(self):
        return self._refreshtoken
    
    @refreshtoken.setter
    def refreshtoken(self, value):
        self._refreshtoken = unicode(value)
    
    @property
    def resource(self):
        return self._resource
    
    @resource.setter
    def resource(self, value):
        self._resource = unicode(value)
    
    @property
    def pushtoken(self):
        return self._pushtoken
    
    @pushtoken.setter
    def pushtoken(self, value):
        self._pushtoken = unicode(value)
    
    @property
    def badgenumber(self):
        return self._badgenumber
    
    @badgenumber.setter
    def badgenumber(self, value):
        self._badgenumber = int(value)
    
    @property
    def pushsound(self):
        return self._pushsound
    
    @pushsound.setter
    def pushsound(self, value):
        self._pushsound = unicode(value)
    
    @property
    def lang(self):
        return self._lang
    
    @lang.setter
    def lang(self, value):
        self._lang = unicode(value)
    
    @property
    def connected(self):
        return self._connected
    
    @connected.setter
    def connected(self, value):
        self._connected = bool(value)

if __name__ == '__main__':
    from twisted.internet import defer, reactor
    
    @defer.inlineCallbacks
    def example():
        user=GoogleUser(_userid="1", _token="accesstoken", _refreshtoken="refreshtoken", _resource="unknownresource", _pushtoken="pushtoken", _badgenumber="0", _pushsound="asdfasdfas")
        yield user.save()
        data = yield user.model.find_one({'appid' : "1"})
        print data
        data2 = yield user.model.find_one({'appid' : "2"})
        print data2
        
        user2 = yield GoogleUser.load("1")
        print user2
        
        user2.badgenumber += 1
        print user2
        
        user3 = yield GoogleUser.load("2")
        print user3
        
    reactor.callLater(1, example)
    reactor.callLater(2, reactor.stop)
    reactor.run()
    
    