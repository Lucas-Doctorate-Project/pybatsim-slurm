"""
Trivial example scheduler that rejects any job.
No hard feelings!
"""

from pybatsim.batsim.batsim import BatsimScheduler


class UniversalRejectionScheduler(BatsimScheduler):
    def onJobSubmission(self, job):
        self.bs.reject_jobs([job])  # nope!
