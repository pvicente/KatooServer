'''
Created on Aug 12, 2013

@author: pvicente
'''
from functools import wraps
from katoo import conf
from katoo.utils.applog import getLogger, getLoggerAdapter
from katoo.utils.patterns import Singleton

log = getLogger(__name__, 'INFO')

class Accumulator(object):
    def __init__(self, source, name, unit):
        self._name = '%s.%s'%(source,name)
        self._unit = unit
        self.reset()
    
    @property
    def name(self):
        return self._name
    
    @property
    def unit(self):
        return self._unit
    
    def reset(self):
        raise NotImplementedError()

class SamplingAccumulator(Accumulator):
    def reset(self):
        self._samples=[]
    
    def add(self, value):
        self._samples.append(value)
    
    def data(self):
        ret = []
        size = len(self._samples)
        
        if size == 0:
            samples_sum = samples_max = samples_min = samples_average = 0.00
        else:
            samples_sum = sum(self._samples)
            samples_max = max(self._samples)
            samples_min = min(self._samples)
            samples_average = samples_sum/(size*1.0)
        
        ret.append('sample#%s=%.2f%s'%(self.name, samples_sum, self.unit))
        ret.append('sample#%s_average=%.2f%s'%(self.name, samples_average, self.unit))
        ret.append('sample#%s_max=%.2f%s'%(self.name, samples_max, self.unit))
        ret.append('sample#%s_min=%.2f%s'%(self.name, samples_min, self.unit))
        
        return ret
    
    def __str__(self):
        return ' '.join(self.data())
    
class SimpleAccumulator(Accumulator):
    def reset(self):
        self._value = 0
    
    def add(self, value):
        self._value+=value
    
    def __str__(self):
        return 'sample#%s=%.2f%s'%(self.name, self._value, self.unit)

class MetricsHub(Singleton):
    def constructor(self):
        self.metrics=[]
    
    def report(self):
        for metric in self.metrics:
            metric.report()
    
class Metric(object):
    log = getLoggerAdapter(log, id='METRIC')
    
    def __init__(self, name, value, unit='', source=conf.MACHINEID, sampling=False, reset=True):
        self._value = value
        self._accumulator = SimpleAccumulator(source, name, unit) if not sampling else SamplingAccumulator(source, name, unit)
        self._reset = reset
        MetricsHub().metrics.append(self)
    
    
    def add(self, value):
        self._accumulator.add(value)
    
    def __call__(self, f):
        @wraps(f)
        def wrapped_f(*args, **kwargs):
            self.add(self._value)
            return f(*args, **kwargs)
        return wrapped_f
    
    def report(self):
        self.log.info(self._accumulator)
        if self._reset:
            self._accumulator.reset()
    
class IncrementMetric(Metric):
    def __init__(self, name, unit=None, source=conf.MACHINEID, reset=True):
        Metric.__init__(self, name, 1, unit=unit, source=source, reset=reset)
