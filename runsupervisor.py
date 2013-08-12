'''
Created on Jul 8, 2013

@author: pvicente
'''
from katoo import KatooApp
from katoo.supervisor import GlobalSupervisor, MetricsSupervisor

application = KatooApp().app

metrics_supervisor = MetricsSupervisor()
metrics_supervisor.setServiceParent(application)

workers_supervisor = GlobalSupervisor()
workers_supervisor.setServiceParent(application)
