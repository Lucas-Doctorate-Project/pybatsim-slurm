"""
This scheduler is a FCFS with DVFS:
- Released jobs are pushed in the back of one single queue
- Two jobs cannot be executed on the same machine at the same time
- Only the job at the head of the queue can be allocated

  - If the job is too big (will never fit the machine), it is rejected
  - If the job can fit the machine now, it is allocated (and started) instantly
  - If the job cannot fit the machine now, the scheduler waits for enough machines to be available

- The DVFS strategy is simple and random:
  - every 10 seconds the scheduler sets a random pstate on every machine executing a job

Let us assume all machines have multiple pstates (with possibly virtual/sleep pstates)
"""

from random import choice
from procset import ProcSet
from itertools import islice

from pybatsim.batsim.batsim import BatsimScheduler


class FcfsWithDVFS(BatsimScheduler):
    def __init__(self, options):
        super().__init__(options)
        self.logger.info("FCFS with DVFS init")

    def onSimulationBegins(self):
        self.nb_completed_jobs = 0

        self.sched_delay = 0.5 # Simulates the time spent by the scheduler to take decisions
        
        self.DVFS_delay = 10 # Random DVFS decisions will be taken every 10 seconds
        self.wake_me_up = True
        self.next_wake_up = 0.0

        self.do_scheduling = False # Only perform a scheduling round when needed
        self.open_jobs = []
        self.nb_running_jobs = 0

        self.computing_machines = ProcSet()
        self.idle_machines = ProcSet((0,self.bs.nb_compute_resources-1))

        self.machines_pstates_list = {}

        for machine_dict in self.bs.machines['compute']:
            # Retrieve the number of pstates for each machine
            watts = machine_dict['properties']['wattage_per_state'].split(", ")
            pstates_list = list(range(len(watts)))

            if 'sleep_pstates' in machine_dict['properties']:
                # But remove the sleep pstates
                sleep_pstates = [int(x) for x in machine_dict['properties']['sleep_pstates'].replace(':', ',').split(',')]
                pstates_list = [x for x in pstates_list if not x in sleep_pstates]

            self.machines_pstates_list[machine_dict['id']] = pstates_list


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
                    job.allocation = res
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
            self.nb_running_jobs += len(scheduled_jobs)
        else:
            # No job to schedule
            self.logger.info("There is no job to schedule right now")


    def onJobSubmission(self, job):
        if job.requested_resources > self.bs.nb_compute_resources:
            self.bs.reject_jobs([job]) # This job requests more resources than the machine has
        else:
            self.open_jobs.append(job)
            self.do_scheduling = True

    def onJobCompletion(self, job):
        self.idle_machines |= job.allocation
        self.computing_machines -= job.allocation

        self.nb_running_jobs -= 1
        self.do_scheduling = True

    def onRequestedCall(self):
        self.do_DVFS()

    def do_DVFS(self):
        self.logger.info("Performing random DVFS")

        for r in self.computing_machines:
            new_pstate = choice(self.machines_pstates_list[r])
            self.bs.set_resource_state(r, new_pstate)

    def onMachinePStateChanged(self, machines, pstate):
        pass


    def onNoMoreEvents(self):
        if self.do_scheduling:
            self.scheduleJobs()
            self.do_scheduling = False

        if self.bs.time() >= self.next_wake_up: # Call a wake up if necessary
            # If jobs are running or more jobs are expected, ask for a wake up for DVFS
            if not self.bs.no_more_static_jobs or (self.nb_running_jobs > 0):
                self.next_wake_up += self.DVFS_delay
                self.bs.wake_me_up_at(self.next_wake_up)

