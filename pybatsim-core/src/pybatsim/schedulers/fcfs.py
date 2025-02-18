"""
This scheduler is a simple FCFS:
- Released jobs are pushed in the back of one single queue
- Two jobs cannot be executed on the same machine at the same time
- Only the job at the head of the queue can be allocated

  - If the job is too big (will never fit the machine), it is rejected
  - If the job can fit the machine now, it is allocated (and run) instantly
  - If the job cannot fit the machine now, the scheduler will waits for enough available machines

"""

from procset import ProcSet
from itertools import islice

from pybatsim.batsim.batsim import BatsimScheduler, JobAllocation


class Fcfs(BatsimScheduler):
    def __init__(self, options):
        super().__init__(options)
        self.logger.info("FCFS init")

    def onBatsimHello(self):
        self.bs.answer_simulation_hello("FCFS", "0.1.0")

    def onSimulationBegins(self):
        self.nb_completed_jobs = 0

        self.sched_delay = 0.5 # Simulates the time spent by the scheduler to take decisions

        self.open_jobs = []

        self.computing_machines = ProcSet()
        self.idle_machines = ProcSet((0,self.bs.nb_compute_resources-1))


    def scheduleJobs(self):
        print('\n\nopen_jobs = ', self.open_jobs)

        print('computingM = ', self.computing_machines)
        print('idleM = ', self.idle_machines)

        scheduled_jobs = []
        loop = True

        # If there is a job to schedule
        if len(self.open_jobs) > 0:

            while loop and self.open_jobs:
                job = self.open_jobs[0]
                nb_res_req = job.requested_resources

                # Job fits now -> allocation
                if nb_res_req <= len(self.idle_machines):
                    res = ProcSet(*islice(self.idle_machines, nb_res_req))
                    job.allocation = JobAllocation(res)
                    scheduled_jobs.append(job)

                    self.computing_machines |= res
                    self.idle_machines -= res
                    self.open_jobs.remove(job)

                else:  # Job can fit on the machine, but not now
                    loop = False

            # update time
            self.bs.consume_time(self.sched_delay)

            # send decision to batsim
            self.bs.execute_jobs(scheduled_jobs)
        else:
            # No job to schedule
            self.logger.info("There is no job to schedule right now")


    def onJobSubmitted(self, job):
        if job.requested_resources > self.bs.nb_compute_resources:
            self.bs.reject_jobs([job]) # This job requests more resources than the machine has
        else:
            self.open_jobs.append(job)

    def onJobCompleted(self, job):
        self.idle_machines |= job.allocation.host_alloc
        self.computing_machines -= job.allocation.host_alloc

    def onNoMoreEvents(self):
        self.scheduleJobs()
