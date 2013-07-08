'''
Created on Jul 8, 2013

@author: pvicente
'''
from katoo import KatooApp
from katoo.supervisor import LocalSupervisor, WorkersSupervisor

application = KatooApp().app

supervisor = LocalSupervisor()
supervisor.setServiceParent(application)

workers_supervisor = WorkersSupervisor()
workers_supervisor.setServiceParent(application)
