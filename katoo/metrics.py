'''
Created on Aug 12, 2013

@author: pvicente
'''
from collections import defaultdict
from functools import wraps
from katoo import conf
from katoo.utils.patterns import Singleton
import logging

#Special log format to filter default format with regular expressions
FORMAT="[%s]"%(conf.MACHINEID)+" %(message)s"
formatter = logging.Formatter(fmt=FORMAT)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
log = logging.getLogger(__name__)
log.addHandler(handler)
log.propagate=False
log.setLevel(logging.INFO)

class Accumulator(object):
    def __init__(self, source, name, unit, scale):
        self._name = ('%s.%s'%(source,name)).replace(' ', '_')
        self._source = source
        self._unit = unit
        self._scale = scale*1.0
        self.reset()
    
    @property
    def name(self):
        return self._name
    
    @property
    def source(self):
        return self._source
    
    @property
    def unit(self):
        return self._unit
    
    def reset(self):
        raise NotImplementedError()

    def __int__(self):
        return 0

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
            samples_sum = sum(self._samples)/self._scale
            samples_max = max(self._samples)/self._scale
            samples_min = min(self._samples)/self._scale
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

    def __int__(self):
        return int(self._value)
    
    def __str__(self):
        return 'sample#%s=%.2f%s'%(self.name, self._value/self._scale, self.unit)

class MetricsHub(Singleton):
    def constructor(self):
        self._metrics=defaultdict(list)
    
    def append(self, metric):
        self._metrics[metric.source].append(metric)
    
    @staticmethod
    def split_output_len(seq, length):
        output = []
        temp=[]
        curr_len = 0
        for i in seq:
            str_len = i[1]
            if curr_len + str_len > length:
                output.append(' '.join(temp))
                temp=[i[0]]
                curr_len = str_len
            else:
                temp.append(i[0])
                curr_len+=i[1]
        
        if temp:
            output.append(' '.join(temp))
        
        return output
    
    def report(self):
        str_metrics = []
        for metrics in self._metrics.itervalues():
            str_metrics.extend(str(metric) for metric in metrics)
        
        output = self.split_output_len(zip(str_metrics, [len(i) for i in str_metrics]), conf.METRICS_OUTPUT_LEN)
        for out in output:
            log.info(out)
    
class Metric(object):
    def __init__(self, name, value, unit='', source=conf.MACHINEID, sampling=False, reset=True, scale=1):
        self._value = value
        self._accumulator = SimpleAccumulator(source, name, unit, scale) if not sampling else SamplingAccumulator(source, name, unit, scale)
        self._reset = reset
        MetricsHub().append(self)
    
    @property
    def source(self):
        return self._accumulator.source
    
    def add(self, value):
        self._accumulator.add(value)

    def __int__(self):
        return int(self._accumulator)

    def __call__(self, f):
        @wraps(f)
        def wrapped_f(*args, **kwargs):
            self.add(self._value)
            return f(*args, **kwargs)
        return wrapped_f
    
    def __str__(self):
        ret = str(self._accumulator)
        if self._reset:
            self._accumulator.reset()
        return ret
    
class IncrementMetric(Metric):
    def __init__(self, name, unit='', source=conf.MACHINEID, reset=True):
        Metric.__init__(self, name, 1, unit=unit, source=source, reset=reset)
