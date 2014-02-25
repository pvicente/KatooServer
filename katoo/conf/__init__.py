'''
Created on May 29, 2013

@author: pvicente
'''
import os, platform

conf_file = os.path.realpath(__file__)
conf_dir = os.path.dirname(conf_file)

#PARAMETERS
MACHINEID='%s.%s'%(platform.node(), os.getpid())
MULTIPROCESS=int(os.getenv('MULTIPROCESS', 0))
TWISTED_WARMUP=int(os.getenv('TWISTED_WARMUP', 2))
TWISTED_SHUTDOWN=int(os.getenv('TWISTED_SHUTDOWN', 3))
LOG_LEVEL=os.getenv('LOG_LEVEL', 'DEBUG')
LOG_FORMAT=os.getenv('LOG_FORMAT', "[%s] "%(MACHINEID)+"[%(levelname)s] [%(filename)s:%(funcName)s:%(lineno)d]")
LOG_RAISE_EXCEPTIONS=eval(str(os.getenv('LOG_RAISE_EXCEPTIONS', True)))
LOGGING_OK_JOBS = eval(str(os.getenv('LOGGING_OK_JOBS', True)))
METRICS_REPORT_TIME = int(os.getenv('METRICS_REPORT_TIME', 60))
METRICS_OUTPUT_LEN = int(os.getenv('METRICS_OUTPUT_LEN', 950))
PRODUCTION=eval(str(os.getenv('PRODUCTION', False)))
LXMLPARSER=eval(str(os.getenv('LXMLPARSER', True)))
TIMER_INTERVAL=int(os.getenv('TIMER_INTERVAL', 1))



#GOOGLE_APP_CREDENTIALS
GOOGLE_CLIENT_ID=os.getenv('GOOGLE_CLIENT_ID', '1066150010031.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET=os.getenv('GOOGLE_CLIENT_SECRET', '8uTcq2n92dDWO8HWaJBC6Lxg')
GOOGLE_OAUTH2_URL='https://accounts.google.com/o/oauth2/token'

#WEBSERVICE
PORT=int(os.getenv('PORT', 5000))
LISTEN=os.getenv('LISTEN', '0.0.0.0')
ADOPTED_STREAM=os.getenv('ADOPTED_STREAM', None)
BACKLOG=int(os.getenv('BACKLOG', 50))
LOG_REQUESTS=eval(str(os.getenv('LOG_REQUESTS', True)))
CYCLONE_DEBUG=eval(str(os.getenv('CYCLONE_DEBUG', True)))
USER_AGENT=os.getenv('USER_AGENT', 'Katoo')
USER_AGENT_CHECK=eval(str(os.getenv('USER_AGENT_CHECK', False)))
USER_AGENT_WL=frozenset(eval(os.getenv('USER_AGENT_WL','[]')))
USER_AGENT_BL=frozenset(eval(os.getenv('USER_AGENT_BL', '[]')))
DEFAULT_VERSION='UNKNOWN'
FAKE_PURCHASE_URL=os.getenv('FAKE_PURCHASE_URL', '')
BACKEND_MAX_RETRIES=int(os.getenv('BACKEND_MAX_RETRIES', 3))
DEFERRED_DEBUG=eval(str(os.getenv('DEFERRED_DEBUG', False)))

##REDIS_CONNECTION_MANAGEMENT
REDIS_WORKERS=int(os.getenv('REDIS_WORKERS', 1))
REDIS_URL=os.getenv('REDISCLOUD_URL', 'redis://localhost:6379')
REDIS_POOL=int(os.getenv('REDIS_POOL', 10))
WORKER_WARMUP=int(os.getenv('WORKER_WARMUP',TWISTED_WARMUP+8))

#MONGO
MONGO_URL=os.getenv('MONGOLAB_URI', 'mongodb://localhost:27017')
MONGO_POOL=int(os.getenv('MONGO_POOL', 10))
MONGO_STORAGE_UNIT=os.getenv('MONGO_STORAGE_UNIT', 'KB')
MONGO_STORAGE_UNIT_SCALE=int(os.getenv('MONGO_STORAGE_UNIT_SCALE', 1024))


#XMPP
XMPP_ROSTER_IN_MEMORY=eval(str(os.getenv('XMPP_ROSTER_IN_MEMORY', False)))
XMPP_LOG_TRAFFIC=eval(str(os.getenv('XMPP_LOG_TRAFFIC', True)))
XMPP_MAX_RETRIES=int(os.getenv('XMPP_MAX_RETRIES', 3))
XMPP_MIN_CONNECTED_TIME=int(os.getenv('XMPP_MIN_CONNECTED_TIME', 60))
XMPP_PRIORITY=int(os.getenv('XMPP_PRIORITY', 0))
XMPP_GTALK_PRIORITY=int(os.getenv('XMPP_GTALK_PRIORITY', 24))
XMPP_MOOD=os.getenv('XMPP_MOOD', "I'm using Katoo iOS!").strip()
XMPP_STATE=os.getenv('XMPP_STATE', 'away')
XMPP_DISCONNECTION_TIME=int(os.getenv('XMPP_DISCONNECTION_TIME', 43200)) #12 hours by default
XMPP_REMOVE_TIME=int(os.getenv('XMPP_REMOVE_TIME', 604800)) #7 days
XMPP_BACKGROUND_TIME=int(os.getenv('XMPP_BACKGROUND_TIME', 180))
XMPP_RESOURCE=os.getenv('XMPP_STATE', 'katooserv')
XMPP_KEEP_ALIVE_TIME=int(os.getenv('XMPP_KEEP_ALIVE_TIME', 300))
XMPP_AUTH_TIMEOUT=int(os.getenv('XMPP_AUTH_TIMEOUT', 60))
XMPP_AUTH_RENEWAL_TIME=int(os.getenv('XMPP_AUTH_RENEWAL_TIME', 3600))

#APNS
APNS_SANDBOX = "sandbox" if not PRODUCTION else "production"
APNS_CERT = conf_dir + ('/certificates/development.pem' if APNS_SANDBOX == 'sandbox' else '/certificates/production.pem')
APNS_TIMEOUT = int(os.getenv('APNS_TIMEOUT', 5))
APNSERVICE_NAME= 'APNS'

#SUPERVISOR
TASK_DISCONNECT_SECONDS = int(os.getenv('TASK_DISCONNECT_SECONDS', 300))
TASK_CHECK_WORKERS = int(os.getenv('TASK_CHECK_WORKERS', 10))
TASK_RECONNECT_ALL_USERS = eval(str(os.getenv('TASK_RECONNECT_ALL_USERS', False)))
SUPERVISOR_WORKER_REFRESH_TIME = int(os.getenv('SUPERVISOR_WORKER_REFRESH_TIME', 60))

#HEROKU
HEROKU_UNIDLING_URL=os.getenv('HEROKU_UNIDLING_URL', None)

#DISTRIBUTED_SYSTEM
DIST_ASYNC_AS_SYNC = eval(str(os.getenv('DIST_ASYNC_AS_SYNC', False)))
DIST_TIMEOUT_TIME = int(os.getenv('DIST_TIMEOUT_TIME', 604800)) #1 week to store job without execution or failed
DIST_DEFAULT_TTL = int(os.getenv('DIST_DEFAULT_TTL', 20))
DIST_PULL_TIME = float(os.getenv('DIST_PULL_TIME', 0.2))
DIST_FIRST_PULL_TIME = float(os.getenv('DIST_FIRST_PULL_TIME', 0.025))
DIST_DISABLED = REDIS_WORKERS == 0
DIST_QUEUE_LOGIN=os.getenv('DIST_QUEUE_LOGIN', 'login')
DIST_QUEUE_RELOGIN=os.getenv('DIST_QUEUE_RELOGIN', 'relogin')
DIST_QUEUE_PUSH=os.getenv('DIST_QUEUE_PUSH', 'push')
DIST_ENQUEUE_FAILED_JOBS=eval(str(os.getenv('DIST_ENQUEUE_FAILED_JOBS', True)))
DIST_PERFORM_JOB_IN_THREAD=eval(str(os.getenv('DIST_PERFORM_JOB_IN_THREAD', True)))
DIST_THREAD_POOL=int(os.getenv('DIST_THREAD_POOL', 10))

