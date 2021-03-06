'''
Created on Jun 4, 2013

@author: pvicente
'''

from datetime import timedelta
import types
from katoo.metrics import IncrementMetric
from katoo.txMongoModel.mongomodel.model import Model, Indexes, Sort
from katoo.txMongoModel.mongomodel import model
from katoo.utils.applog import getLogger, getLoggerAdapter
from katoo.utils.connections import MongoMixin
from katoo.utils.time import Timer, sleep
from twisted.internet import defer
from txmongo._pymongo.objectid import ObjectId
import conf

log = getLogger(__name__)

METRIC_UNIT='calls'
METRIC_SOURCE='DATA'

Model.METRIC_SAVE = IncrementMetric(name='SavingErrors', unit=METRIC_UNIT, source='MONGO', reset=False)
Model.METRIC_RETRY = IncrementMetric(name='ErrorRetries', unit=METRIC_UNIT, source='MONGO', reset=False)
Model.MAX_RETRY = conf.BACKEND_MAX_RETRIES
Model.RETRY_DELAY = conf.BACKEND_MAX_DELAY
model.SLEEP_TIME_FUNC = sleep

class ModelMixin(Model, MongoMixin):
    def __init__(self, collectionName, mongourl=None, indexes=None):
        self.setup(url=mongourl)
        self.db = self.mongo_db
        self.collection = collectionName
        self.pool = self.mongo_conn
        self.indexes = indexes
        logger = getLoggerAdapter(log, id="DATA-%s"%(collectionName.upper()))
        Model.__init__(self, logging=logger)
    
class DataModel(ModelMixin):
    def __init__(self, collectionName, mongourl=None, indexes=None):
        ModelMixin.__init__(self, collectionName, mongourl=mongourl, indexes=indexes)

class GoogleMessage(object):
    model = DataModel(collectionName='googlemessages', indexes=Indexes(['userid', ('time', 'msgid'),  dict(fields='removeTime', expireAfterSeconds=conf.XMPP_REMOVE_TIME)]))
    
    @classmethod
    def getMessages(cls, userid):
        return cls.model.find(spec={'userid':userid}, fields={'_id':0, 'time':1, 'fromid':1, 'msgid':1, 'data':1}, mongofilter=Sort.getFilter(['time', 'msgid']))
    
    @classmethod
    def flushMessages(cls, userid):
        return cls.model.remove({'userid':userid})
    
    @classmethod
    def updateRemoveTime(cls, userid, time):
        return cls.model.update(spec={'userid':userid}, multi=True, **{'$set': { 'removeTime': time}})
    
    def __init__(self, userid, fromid, msgid, data):
        self.userid = userid
        self.fromid = fromid
        self.msgid = msgid
        self.data = data
        self.time = Timer().isoformat() 
        self.removeTime=None
    
    def save(self):
        data=vars(self)
        return self.model.save(data)

class GoogleRosterItem(object):
    model = DataModel(collectionName='googleroster', indexes=Indexes(['_userid', ('_userid','_jid')]))
    
    @classmethod
    @IncrementMetric(name='rosteritem_exists', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def exists(cls, userid):
        d = cls.model.find_one(spec={'_userid': userid})
        d.addCallback(lambda result: None if not result else cls(**result))
        return d
    
    @classmethod
    @IncrementMetric(name='rosteritem_remove', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def remove(cls, userid, jid=None):
        if jid is None:
            return cls.model.remove({'_userid': userid})
        else:
            return cls.model.remove({'_userid': userid, '_jid': jid})
    
    @classmethod
    @IncrementMetric(name='rosteritem_load', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def load(cls, userid, jid):
        d = cls.model.find_one(spec={'_userid': userid, '_jid': jid})
        d.addCallback(lambda result: None if not result else cls(**result))
        return d
    
    def __init__(self, _userid, _jid, _name=None, _contactName=None, _favorite=False, _snoozePushTime=None, _notifyWhenAvailable=None, _id=None):
        self._userid = _userid
        self._jid = _jid
        self._name = _name
        self._contactName = _contactName
        self._favorite = bool(_favorite)
        self._snoozePushTime = _snoozePushTime
        self._notifyWhenAvailable = _notifyWhenAvailable
        if isinstance(_id, ObjectId):
            self._id = _id
    
    @IncrementMetric(name='rosteritem_save', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def save(self):
        return self.model.save(vars(self))
    
    def update(self, **kwargs):
        for k,v in kwargs.iteritems():
            setattr(self,k,v);
    
    def __str__(self):
        return '<%s object at %s>(%s)'%(self.__class__.__name__, hex(id(self)), vars(self))
    
    def __repr__(self):
        return '<%s object at %s (_id:%s, appid:%s)>'%(self.__class__.__name__, hex(id(self)), getattr(self, '_id', None), self.userid)
    
    @property
    def userid(self):
        return self._userid
    
    @property
    def jid(self):
        return self._jid
    
    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, value):
        self._name = u' '.join(value.split()[:2])
        if self.contactName is None:
            self.contactName = self._name
    
    @property
    def contactName(self):
        return self._contactName
    
    @contactName.setter
    def contactName(self, value):
        if value:
            self._contactName = u' '.join(value.split()[:2])
        else:
            self._contactName = self.name
    
    @property
    def favorite(self):
        return self._favorite
    
    @favorite.setter
    def favorite(self, value):
        if isinstance(value, types.StringTypes):
            value = int(value) if value.isdigit() else ''
        self._favorite = bool(value)
    
    @property
    def favoriteEmoji(self):
        return u'\ue32f' if self._favorite else ''
    
    @property
    def snoozePushTime(self):
        return False if self._snoozePushTime is None else Timer().utcnow() <= self._snoozePushTime
    
    @snoozePushTime.setter
    def snoozePushTime(self, value):
        if value:
            seconds = int(value)
            self._snoozePushTime = Timer().utcnow()+timedelta(seconds=seconds) if seconds else Timer().utcnow() + timedelta(days=365)
        else:
            self._snoozePushTime = None
    
    @property
    def notifyWhenAvailable(self):
        return False if self._notifyWhenAvailable is None else Timer().utcnow() <= self._notifyWhenAvailable
    
    @notifyWhenAvailable.setter
    def notifyWhenAvailable(self, value):
        if value:
            seconds = int(value)
            self._notifyWhenAvailable = Timer().utcnow() + timedelta(seconds=seconds)
        else:
            self._notifyWhenAvailable = None
    
class GoogleUser(object):
    model = DataModel(collectionName='googleusers', indexes=Indexes([dict(fields='_userid', unique=True), '_pushtoken', ('_userid, _jid'), ('_connected','_away', '_lastTimeConnected'),
                                                                     ('_connected', '_worker'), ('_connected', '_onMigrationTime', '_onReloging'), dict(fields='_lastTimeConnected', expireAfterSeconds=conf.XMPP_REMOVE_TIME) ]))
    
    @classmethod
    @IncrementMetric(name='googleuser_load', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def load(cls, userid=None, jid=None, pushtoken=None):
        if userid is None and jid is None and pushtoken is None:
            return defer.returnValue(None)
        search_filter = dict([('_'+k,v) for k,v in locals().iteritems() if k != 'cls' and not v is None])
        d = cls.model.find_one(search_filter)
        d.addCallback(lambda result: None if not result else cls(**result))
        return d
    
    @classmethod
    @IncrementMetric(name='googleuser_remove', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def remove(cls, userid, flush_messages=True):
        if flush_messages:
            return defer.DeferredList([cls.model.remove({'_userid': userid}), GoogleMessage.flushMessages(userid), GoogleRosterItem.remove(userid)])
        else:
            return defer.DeferredList([cls.model.remove({'_userid': userid}), GoogleRosterItem.remove(userid)])
    
    @classmethod
    def get_connected(cls, worker_name=None):
        if worker_name is None:
            return cls.model.find(spec={'_connected': True})
        else:
            return cls.model.find(spec={'_connected': True, '_worker': worker_name})
    
    @classmethod
    def get_assigned_workers(cls):
        return cls.get_distinct(key='_worker', spec={'_connected': True, '_onReloging': False})
    
    @classmethod
    def get_away(cls):
        disconnected_time = Timer().utcnow() - timedelta(seconds=conf.XMPP_DISCONNECTION_TIME)
        return cls.model.find(spec={'_connected': True, '_away': True, '_lastTimeConnected': {"$lt": disconnected_time}})
    
    @classmethod
    def get_onMigration(cls):
        return cls.model.find(spec={'_connected': True, '_onMigrationTime': {'$ne': ''}})
    
    @classmethod
    def get_distinct(cls, key, spec={'_connected': True}):
        if spec:
            return cls.model.distinct(key=key, spec=spec)
        else:
            return cls.model.distinct(key=key)
    
    def __init__(self,
                 _userid, 
                 _jid,
                 _token,
                 _refreshtoken,
                 _resource,
                 _pushtoken = '',
                 _badgenumber = 0,
                 _pushsound = '',
                 _favoritesound= '',
                 _lang= 'en-US',
                 _connected=True,
                 _away=False,
                 _id = None,
                 _lastTimeConnected=None,
                 _worker=conf.MACHINEID,
                 _onMigrationTime='',
                 _onReloging=False,
                 _availablePresenceContacts = {},
                 _version=conf.DEFAULT_VERSION,
                 _iosversion=conf.DEFAULT_VERSION,
                 _hwmodel=conf.DEFAULT_VERSION
                 ):
        self._userid = unicode(_userid)
        self._jid = unicode(_jid)
        self._token = unicode(_token)
        self._refreshtoken = unicode(_refreshtoken)
        self._resource = unicode(_resource)
        self._pushtoken = unicode(_pushtoken)
        self._badgenumber = int(_badgenumber)
        self._pushsound = unicode(_pushsound)
        self._favoritesound = unicode(_favoritesound)
        self._lang = unicode(_lang)
        self._connected = bool(_connected)
        self._away = bool(_away)
        self._lastTimeConnected=_lastTimeConnected
        self._worker=_worker
        self._onMigrationTime=_onMigrationTime
        self._onReloging = bool(_onReloging)
        self._availablePresenceContacts = _availablePresenceContacts
        self._version = _version
        self._iosversion = _iosversion
        self._hwmodel = _hwmodel
        if isinstance(_id, ObjectId):
            self._id = _id
    
    @IncrementMetric(name='googleuser_save', unit=METRIC_UNIT, source=METRIC_SOURCE)
    def save(self):
        return self.model.save(vars(self))
    
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
    def jid(self):
        return self._jid
    
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
        #If a new resource is setted away state is setted to False
        self.away = False
    
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
    def favoritesound(self):
        return self._favoritesound
    
    @favoritesound.setter
    def favoritesound(self, value):
        self._favoritesound = unicode(value)
    
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
    
    @property
    def away(self):
        return self._away
    
    @away.setter
    def away(self, value):
        self._away = bool(value)
        if self._away:
            if self._lastTimeConnected is None:
                self._lastTimeConnected = Timer().utcnow()
        else:
            self._lastTimeConnected = None
    
    @property
    def lastTimeConnected(self):
        return self._lastTimeConnected
    
    @property
    def worker(self):
        return self._worker
    
    @worker.setter
    def worker(self, value):
        self._worker=value
        self._onReloging = (value == self.userid)
    
    @property
    def onMigrationTime(self):
        return self._onMigrationTime
    
    @onMigrationTime.setter
    def onMigrationTime(self, value):
        self._onMigrationTime=value
    
    @property
    def onReloging(self):
        return self._onReloging
    
    def addAvailablePresenceContact(self, jid):
        self._availablePresenceContacts[jid] = None
    
    def removeAvailablePresenceContact(self, jid):
        self._availablePresenceContacts.pop(jid, None)
    
    def isContactInAvailablePresence(self, jid):
        return jid in self._availablePresenceContacts
    
    def haveAvailablePresenceContacts(self):
        return True if self._availablePresenceContacts else False
    
if __name__ == '__main__':
    from twisted.internet import reactor
    
    @defer.inlineCallbacks
    def example_users():
        indexes = GoogleUser.model.indexes
        for index in indexes.indexes:
            res = yield GoogleUser.model.ensure_index(index)
            print res

        user=GoogleUser(_userid="1", _token="accesstoken", _refreshtoken="refreshtoken", _resource="unknownresource", _pushtoken="pushtoken", _badgenumber="0", _pushsound="asdfasdfas", _jid='kk@gmail.com')
        user.away=True
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
        
        #With pushtoken duplicated
        dup_user = GoogleUser(_userid="2", _jid="kk@gmail.com", _token="accesstoken", _refreshtoken="refreshtoken", _resource="12345", _pushtoken="pushtoken")
        ret = yield dup_user.save()
        print ret
        
        res = yield GoogleUser.get_away()
        print "Away user to be disconnected", res
        
        res = yield user.remove(user.userid)
        print res
    
    reactor.callLater(1, example_users)
    reactor.callLater(10, reactor.stop)
    reactor.run()
    
    