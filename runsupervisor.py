'''
Created on Jul 8, 2013

@author: pvicente
'''
from katoo import KatooApp
from katoo.supervisor import LocalSupervisor, GlobalSupervisor

application = KatooApp().app

supervisor = LocalSupervisor()
supervisor.setServiceParent(application)

workers_supervisor = GlobalSupervisor()
workers_supervisor.setServiceParent(application)
