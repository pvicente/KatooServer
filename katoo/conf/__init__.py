'''
Created on May 29, 2013

@author: pvicente
'''
import os

conf_file = os.path.realpath(__file__)
conf_dir = os.path.dirname(conf_file)

#GOOGLE_APP_CREDENTIALS
GOOGLE_CLIENT_ID=os.getenv('GOOGLE_CLIENT_ID', '1066150010031.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET=os.getenv('GOOGLE_CLIENT_SECRET', '8uTcq2n92dDWO8HWaJBC6Lxg')
GOOGLE_OAUTH2_URL='https://accounts.google.com/o/oauth2/token'

#WEBSERVICE
PORT=int(os.getenv('PORT', 5000))
LISTEN=os.getenv('LISTEN', '0.0.0.0')
LOG_REQUESTS=eval(str(os.getenv('LOG_REQUESTS', True)))
CYCLONE_DEBUG=eval(str(os.getenv('CYCLONE_DEBUG', True)))

##REDIS_CONNECTION_MANAGEMENT
REDIS_WORKERS=int(os.getenv('REDIS_WORKERS', 1))
REDIS_URL=os.getenv('REDISCLOUD_URL', 'redis://localhost:6379')
REDIS_POOL=int(os.getenv('REDIS_POOL', 10))

#MONGO
MONGO_URL=os.getenv('MONGOLAB_URI', 'mongodb://localhost:27017')
MONGO_POOL=int(os.getenv('MONGO_POOL', 10))

#XMPP
XMPP_ROSTER_IN_MEMORY=eval(str(os.getenv('XMPP_ROSTER_IN_MEMORY', True)))
XMPP_LOG_TRAFFIC=eval(str(os.getenv('XMPP_LOG_TRAFFIC', True)))
XMPP_MAX_RETRIES=int(os.getenv('XMPP_MAX_RETRIES', 3))
XMPP_MIN_CONNECTED_TIME=int(os.getenv('XMPP_MIN_CONNECTED_TIME', 60))
XMPP_PRIORITY=int(os.getenv('XMPP_PRIORITY', 0))
XMPP_STATE=os.getenv('XMPP_STATE', 'away')
XMPP_RESOURCE=os.getenv('XMPP_STATE', 'server')
XMPP_DISCONNECTION_TIME=int(os.getenv('XMPP_DISCONNECTION_TIME', 28800)) #8 hours by default
XMPP_REMOVE_TIME=int(os.getenv('XMPP_REMOVE_TIME', 604800)) #7 days

#APNS
APNS_SANDBOX = "sandbox" if os.getenv('PRODUCTION', None) is None else "production"
APNS_CERT = conf_dir + ('/certificates/development.pem' if APNS_SANDBOX else '/certificates/production.pem')
APNS_TIMEOUT = int(os.getenv('APNS_TIMEOUT', 5))
APNSERVICE_NAME= 'APNS'

#SUPERVISOR
TASK_DISCONNECT_SECONDS = int(os.getenv('TASK_DISCONNECT_SECONDS', 300))

#HEROKU
HEROKU_UNIDLING_URL=os.getenv('HEROKU_UNIDLING_URL', None)