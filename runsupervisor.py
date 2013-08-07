'''
Created on Jul 8, 2013

@author: pvicente
'''
from katoo import KatooApp
from katoo.supervisor import GlobalSupervisor

application = KatooApp().app

workers_supervisor = GlobalSupervisor()
workers_supervisor.setServiceParent(application)
