'''
Created on May 25, 2013

@author: pvicente
'''
import inspect

def for_methods(method_list, decorator):
    methods = set(method_list)
    def decorate(cls):
        ret = cls
        for cls in inspect.getmro(cls):
            for attr in [v for v in cls.__dict__ if v in methods]:
                tmp = getattr(cls,attr)
                if callable(tmp):
                    setattr(cls, attr, decorator(tmp))
        return ret
    return decorate
