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
    def __init__(self):
        self._samples=[]
    
    def add(self, value):
        self._samples.append(value)
    
    def data(self):
        ret = dict()
        size = len(self._samples)
        if size == 0:
            return ret

        samples_sum = sum(self._samples)
        samples_max = max(self._samples)
        samples_min = min(self._samples)
        samples_average = samples_sum/(size*1.0)
        
        ret['sum'] = samples_sum
        
        if size > 1:
            ret['average'] = samples_average
        
        if samples_max != samples_min:
            ret['max'] = samples_max
            ret['min'] = samples_min
        
        return ret

class MetricsHub(Singleton):
    def constructor(self):
        self.metrics=[]
    
    def report(self):
        for metric in self.metrics:
            metric.report()
    
class Metric(object):
    log = getLoggerAdapter(log, id='METRIC')
    
    def __init__(self, name, value, unit=None, source=conf.MACHINEID, average=False):
        self._source = source
        self._name = name
        self._value = value
        self._unit = '' if unit is None else ' units=%s'%(unit)
        self._average=average
        self._accumulator = Accumulator()
        MetricsHub().metrics.append(self)
        self._nodata_string='source=%s measure=%s val=0.00%s'%(self._source, self._name, self._unit)
    
    def __call__(self, f):
        @wraps(f)
        def wrapped_f(*args, **kwargs):
            self._accumulator.add(self._value)
            return f(*args, **kwargs)
        return wrapped_f
    
    def report(self):
        data = self._accumulator.data()
        if data:
            for key,value in data.iteritems():
                meassure = self._name
                if key == 'average' and not self._average:
                    continue
                if key != 'sum':
                    meassure='%s_%s'%(self._name, key)
                self.log.info('source=%s measure=%s val=%.2f%s',self._source, meassure, value, self._unit)
            self._accumulator = Accumulator()
        else:
            self.log.info(self._nodata_string)

class IncrementMetric(Metric):
    def __init__(self, name, unit=None, source=conf.MACHINEID):
        Metric.__init__(self, name, 1, unit=unit, source=source)
