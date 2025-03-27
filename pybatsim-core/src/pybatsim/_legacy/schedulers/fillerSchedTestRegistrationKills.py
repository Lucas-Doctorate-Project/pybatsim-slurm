from itertools import islice

from procset import ProcSet

from pybatsim.batsim.batsim import BatsimScheduler, JobAllocation
import logging

class FillerSchedTest(BatsimScheduler):
    def __init__(self, options):
        super().__init__(options)
        self.logger.setLevel(logging.INFO)

        self.logger.info("Filler sched for testing purposes")
        #self.logger.setLevel(logging.CRITICAL)

    def onAfterBatsimInit(self, init_str):
        self.logger.info(f"Received init str: {init_str}")
        #pass # Do nothing

    def onBatsimHello(self):
        # Modify some simulation context parameters

        # Ask for the forwarding of profiles on job submission
        self.bs.simulation_context.forward_profiles_on_simulation_begins = True
        self.bs.simulation_context.forward_profiles_on_job_submission = True
        self.bs.simulation_context.forward_profiles_on_jobs_killed = True
        self.bs.simulation_context.dynamic_registration = True
        self.bs.simulation_context.profile_reuse = True
        self.bs.simulation_context.acknowledge_dynamic_jobs = True


        self.bs.answer_simulation_hello("FillerSchedTest", "0.1.0")

    def onSimulationBegins(self):
        self.nb_completed_jobs = 0

        self.jobs_completed = []
        self.jobs_waiting = []

        self.sched_delay = 0.005

        self.default_placement_type = JobAllocation.ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper
        #self.default_placement_strategy = JobAllocation.ExecutorPlacementStrategy.FillOneHostCoresFirst # Leads to internal inconsistency in batsim
        self.default_placement_strategy = JobAllocation.ExecutorPlacementStrategy.SpreadOverHostsFirst

        self.openJobs = set()
        self.availableResources = ProcSet((0,self.bs.nb_compute_resources-1))

        self.bs.call_me_later_once("oneshot", 1)
        self.bs.call_me_later_once("oneshot2", 2)
        
        # TODO: Test the periodic calls with non-zero offset when it's implemented in Batsim
        #self.bs.call_me_later_periodic("periodic_finite", 3, 5, 5)
        #self.bs.call_me_later_periodic("periodic_infinite", 0, 10, -1)
        self.kill_periodic_finite = True # Whether to stop the periodic call me later or not

        # if self.bs.simulation_context.forward_profiles_on_simulation_begins:
        #     print("Got the profiles from SIMULATION_BEGINS:")
        #     for wl in self.bs.workloads.keys():
        #         print("In workload", wl)
        #         for prof in self.bs.profiles[wl].values():
        #             print(prof)

        self.kill_toto = False



    def scheduleJobs(self):
        scheduledJobs = []

        # consume time to simulate time spent planning the schedule
        self.bs.consume_time(self.sched_delay)

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

                if job.job_id == "w0!toto":
                    self.kill_toto = True

        # send to uds
        if len(scheduledJobs) > 0:
            self.bs.execute_jobs(scheduledJobs)

    def onJobSubmitted(self, job):
        if job.requested_resources > self.bs.nb_compute_resources:
            self.bs.reject_job_by_id(job.job_id) # This job requests more resources than the machine has
        else:
            self.openJobs.add(job)

        profile_workload = job.profile_id.split(self.bs.WORKLOAD_JOB_SEPARATOR)[0]

        prof = self.bs.profiles[profile_workload][job.profile_id]
        print(f"New job {job.job_id} submitted with profile", prof)

    def onJobCompleted(self, job):
        self.availableResources |= job.allocation.host_alloc

    def onNoMoreEvents(self):
        self.scheduleJobs()
        if self.kill_toto:
            print("====== Asking to kill toto")
            self.bs.kill_jobs_by_ids(["w0!toto"])
            self.kill_toto = False


    def onJobsKilled(self, jobs):
        pass


    def onRequestedCall(self, call_me_later_id, last_periodic_call):
        self.logger.info(f"Got requested call from id {call_me_later_id} (last call? {last_periodic_call}")


        if call_me_later_id == "oneshot":
            self.bs.kill_jobs_by_ids(["w0!hom1"])
            #self.bs.force_simulation_stop()
        elif call_me_later_id == "oneshot2":
            self.bs.kill_jobs_by_ids(["dyn-beta!j3"])

        # The periodic call me later has finished, no need to stop it when receiving NoMoreJobsInWorkloads event
        if last_periodic_call:
            self.kill_periodic_finite = False

    def onAllStaticJobsHaveBeenSubmitted(self):
        # Test various dynamic jobs
        # Register a dynamic job in static workload with static profile
        jid1 = "w0!toto" # re-use the static workload
        profid1 = "w0!delay10" # re-use the profile of the static workload
        self.bs.register_job(jid1, profid1, 30, 1, "{\"toto\": \"tata\"}")

        # Register a new profile in new dynamic workload
        prof_name = "ptask_homo"
        prof_type = "ParallelTaskHomogeneousProfile"
        prof_dict = {
            "computation_amount": 100000000.0,
            "communication_amount": 81920.0,
            "generation_strategy": "DefinedAmountsUsedForEachValue"
        }
        self.bs.register_profile("dyn-workload", prof_name, prof_type, prof_dict)

        # Then register one job in static workload and one in dynamic workload using that profile
        # Job of ptask_homo profile with 1 resource asked
        jid2 = "w0!hom1"
        self.bs.register_job(jid2, "dyn-workload!"+prof_name, -1, 1)

        # Job of ptask_homo profile with 4 resources asked
        jid3 = "dyn-workload!hom4"
        self.bs.register_job(jid3, prof_name, 50, 4)

        # Register a profile in the static workload
        self.bs.register_profile("dyn-alpha", "static_profile", "DelayProfile", {"delay": 500})

        new_job = self.bs.register_job("dyn-beta!j3", "dyn-alpha!static_profile", -1, 1);

        # host_alloc = ProcSet(*islice(self.availableResources, 1))
        # new_job.allocation = JobAllocation(host_alloc, self.default_placement_type, self.default_placement_strategy)
        # self.availableResources -= host_alloc
        # self.bs.execute_jobs([new_job])

        ##### TODO: check also the different asserts and possible errors of job/profile registrations
        # like job or profile already existing in the workload
        # try registering a profile in a new workload + a job in another new workload


        # The notify Batsim that dynamic registrations are finished
        self.bs.finish_registration()

        self.bs.stop_call_me_later("periodic_infinite")

        # if self.kill_periodic_finite:
        #     self.bs.stop_call_me_later("periodic_finite")
