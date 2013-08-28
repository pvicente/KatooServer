'''
Created on Jun 28, 2013

@author: pvicente
'''
from threading import RLock
from twisted.internet import defer

class Singleton(object):
    _instance = None
    _lock = RLock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance == None:
            with cls._lock:
                #Be sure that we only construct one object
                if cls._instance == None:
                    temp = super(Singleton, cls).__new__(
                                        cls, *args, **kwargs)
                    temp.constructor(*args, **kwargs)
                    cls._instance = temp
        return cls._instance
    
    def __init__(self, *args, **kwargs):
        pass
    
    def constructor(self, *args, **kwargs):
        raise NotImplementedError('Must be implemented in subclass to do the first construction')

class Observer(object):
    def notify(self):
        raise NotImplementedError()

class Subject(object):
    def __init__(self):
        self._observers = set()
    
    def registerObserver(self, observer):
        self._observers.add(observer)
    
    def unregisterObserver(self, observer):
        self._observers.remove(observer)
    
    @defer.inlineCallbacks
    def notifyObservers(self):
        for observer in self._observers:
            yield observer.notify()
