from random import sample

from procset import ProcSet

from pybatsim.batsim.batsim import BatsimScheduler, JobAllocation


class RandomSched(BatsimScheduler):

    def onBatsimHello(self):
        self.bs.answer_simulation_hello("Random", "0.1.0")

    def onSimulationBegins(self):
        self.res = [x for x in range(self.bs.nb_compute_resources)]
        self.jobs_res = {}
        self.openJobs = set()
        self.sched_delay = 0

    def scheduleJobs(self):
        scheduledJobs = []

        # Iterating over all open jobs
        for job in self.openJobs:
            res = sample(self.res, job.requested_resources)
            job.allocation = JobAllocation(ProcSet(*res))
            self.jobs_res[job.job_id] = res
            scheduledJobs.append(job)

        # Clearing open jobs
        self.openJobs = set()

        # update time
        self.bs.consume_time(self.sched_delay)

        # send to uds
        if len(scheduledJobs) > 0:
            self.bs.execute_jobs(scheduledJobs)

    def onJobSubmitted(self, job):
        if job.requested_resources > self.bs.nb_compute_resources:
            self.bs.reject_jobs([job]) # This job requests more resources than the machine has
        else:
            self.openJobs.add(job)

    def onJobCompleted(self, job):
        pass

    def onNoMoreEvents(self):
        self.scheduleJobs()
