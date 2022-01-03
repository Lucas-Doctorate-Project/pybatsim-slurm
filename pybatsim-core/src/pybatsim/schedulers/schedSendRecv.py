"""
    schedSendRecv
    ~~~~~~~~~~~~~

    Simple scheduler to show the send and receive messages. Should be used with
    a workload consisting of send and receive profiles.

"""

from pybatsim.batsim.sched import Scheduler
from pybatsim.batsim.sched.algorithms.filling import filler_sched
from pybatsim.batsim.sched.algorithms.utils import consecutive_resources_filter


class SchedSendRecv(Scheduler):

    def on_job_message(self, job, message):
        if message.type == "accept":
            job.send("accepted")
        else:
            job.send("denied")

    def schedule(self):
        return filler_sched(
            self,
            resources_filter=consecutive_resources_filter,
            abort_on_first_nonfitting=False)
