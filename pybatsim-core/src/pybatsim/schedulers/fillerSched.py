from itertools import islice

from procset import ProcSet

from pybatsim.batsim.batsim import BatsimScheduler, JobAllocation
import logging

class FillerSched(BatsimScheduler):
    def __init__(self, options):
        super().__init__(options)
        self.logger.setLevel(logging.INFO)

        self.logger.info("Filler sched init")
        #self.logger.setLevel(logging.CRITICAL)

    def onAfterBatsimInit(self, init_str):
        self.logger.info(f"Received init str: {init_str}")
        #pass # Do nothing

    def onBatsimHello(self):
        # Ask for the forwarding of profiles on job submission
        # TODO not implemented yet on Batsim side
        #self.bs.simulation_context.forward_profiles_on_job_submission = True

        self.bs.answer_simulation_hello("FillerSched", "0.1.0")

    def onSimulationBegins(self):
        self.nb_completed_jobs = 0

        self.jobs_completed = []
        self.jobs_waiting = []

        self.sched_delay = 0.005

        self.default_placement_type = JobAllocation.ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper
        self.default_placement_strategy = JobAllocation.ExecutorPlacementStrategy.FillOneHostCoresFirst
        #self.default_placement_strategy = JobAllocation.ExecutorPlacementStrategy.SpreadOverHostsFirst

        self.openJobs = set()
        self.availableResources = ProcSet((0,self.bs.nb_compute_resources-1))


    def scheduleJobs(self):
        scheduledJobs = []

        print('openJobs = ', self.openJobs)
        print('available = ', self.availableResources)

        # Iterating over a copy to be able to remove jobs from openJobs at traversal
        for job in set(self.openJobs):
            nb_res_req = job.requested_resources

            if nb_res_req <= len(self.availableResources):
                # Retrieve the *nb_res_req* first availables resources
                host_alloc = ProcSet(*islice(self.availableResources, nb_res_req))
                job.allocation = JobAllocation(host_alloc, self.default_placement_type, self.default_placement_strategy)
                scheduledJobs.append(job)

                self.availableResources -= host_alloc

                self.openJobs.remove(job)

        # update time
        self.bs.consume_time(self.sched_delay)

        # send to uds
        if len(scheduledJobs) > 0:
            self.bs.execute_jobs(scheduledJobs)

        print('openJobs = ', self.openJobs)
        print('available = ', self.availableResources)
        print('')

    def onJobSubmission(self, job):
        if job.requested_resources > self.bs.nb_compute_resources:
            self.bs.reject_jobs([job]) # This job requests more resources than the machine has
        else:
            self.openJobs.add(job)

    def onJobCompletion(self, job):
        self.availableResources |= job.allocation.host_alloc

    def onNoMoreEvents(self):
        self.scheduleJobs()
