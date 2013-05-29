'''
Created on May 29, 2013

@author: pvicente
'''
from urlparse import urlparse

def redis_url_parse(url):
    url = urlparse(url)
    
    # We only support redis:// schemes.
    assert url.scheme == 'redis' or not url.scheme
    
    # Extract the database ID from the path component if hasn't been given.
    try:
        db = int(url.path.replace('/', ''))
    except (AttributeError, ValueError):
            db = 0
    
    return (url.hostname, url.port or 6379, db, url.password)