from pybatsim.batsim.batsim import BatsimScheduler, JobAllocation

import sys
import os
import logging
from procset import ProcSet
from itertools import islice


class TestSched(BatsimScheduler):
    def __init__(self, options):
        super().__init__(options)
        self.logger.setLevel(logging.INFO)

        self.logger.info("This is a test")
        self.logger.info(f"Options: -{options}-")
        self.logger.setLevel(logging.CRITICAL)

    def onBatsimHello(self):
        #self.bs.simulation_context.dynamic_registration = True
        #self.bs.simulation_context.acknowledge_dynamic_jobs = True
        #self.bs.simulation_context.forward_profiles_on_job_submission = True
        #self.bs.simulation_context.forward_profiles_on_simulation_begins = True
        #self.bs.simulation_context.profile_reuse = True

        self.bs.answer_simulation_hello("PybatTest", "0.1")


    def onSimulationBegins(self):
        self.nb_completed_jobs = 0

        self.jobs_completed = []
        self.jobs_waiting = []

        self.sched_delay = 1

        self.openJobs = set()
        self.availableResources = ProcSet((0,self.bs.nb_compute_resources-1))


        #Register a new profile in new dynamic workload
        # prof_name = "preplay"
        # prof_type = "TraceReplayProfile"
        # prof_dict = {
        #     "trace_type": "FractionalComputation",
        #     "filename": "../workloads/usage-trace/homo-onephase-50/traces.txt"
        # }
        # self.bs.register_profile("dyn", prof_name, prof_type, prof_dict)

        # jid2 = "dyn!jreplay"
        # self.bs.register_job(jid2, "dyn!preplay", -1, 2)

        # self.bs.finish_registration()

        #self.bs.call_me_later_once("oneshot", 40)


    # def onRequestedCall(self, call_me_later_id, last_periodic_call):
    #     prof_name = "psequence"
    #     prof_type = "SequentialCompositionProfile"
    #     prof_dict = {
    #         "repetition_count" : 1,
    #         "profile_ids": ["w0!simple", "w0!homogeneous_no_cpu", "w0!simple", "w0!homogeneous_no_com"]
    #     }
    #     self.bs.register_profile("w0", prof_name, prof_type, prof_dict)

    #     self.bs.register_job("w0!jsequence", "w0!psequence", -1, 4)

    #     self.bs.finish_registration()


    def scheduleJobs(self):
        scheduledJobs = []

        # Iterating over a copy to be able to remove jobs from openJobs at traversal
        for job in set(self.openJobs):
            nb_res_req = job.requested_resources

            if nb_res_req <= len(self.availableResources):
                # Retrieve the *nb_res_req* first availables resources
                job_alloc = ProcSet(*islice(self.availableResources, nb_res_req))
                job.allocation = JobAllocation(job_alloc)
                scheduledJobs.append(job)

                self.availableResources -= job_alloc

                self.openJobs.remove(job)

        # update time
        self.bs.consume_time(self.sched_delay)

        # send to Batsim
        if len(scheduledJobs) > 0:
            self.bs.execute_jobs(scheduledJobs)
            job_ids = [job.job_id for job in scheduledJobs]
            self.logger.info(f"Starting these jobs: {job_ids}")


    def onJobSubmitted(self, job):
        if job.requested_resources > self.bs.nb_compute_resources:
            self.bs.reject_job_by_id(job.job_id) # This job requests more resources than the machine has
        else:
            self.openJobs.add(job)
            self.scheduleJobs()
        #self.bs.reject_job_by_id(job.job_id)

    def onJobCompleted(self, job):
        self.availableResources |= job.allocation.host_alloc
        self.scheduleJobs()

    def onExternalEventOccurred(self, event_type, event_data):
        print(f"External event occurred! Type: {event_type}, data: {event_data}")
