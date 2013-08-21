'''
Created on May 25, 2013

@author: pvicente
'''
import inspect

def inject_decorators(method_decorator_dict):
    def decorate(cls):
        ret = cls
        for cls in inspect.getmro(cls):
            for attr in [v for v in cls.__dict__ if v in method_decorator_dict.keys()]:
                tmp = getattr(cls,attr)
                if callable(tmp):
                    setattr(cls, attr, method_decorator_dict[attr](tmp))
        return ret
    return decorate

def inject_decorator(method_list, decorator):
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
