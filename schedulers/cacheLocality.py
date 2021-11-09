from batsim.batsim import BatsimScheduler, Batsim

import sys
import os
import time
import json
import math
from procset import ProcSet
from itertools import islice


class CacheLocality(BatsimScheduler):

    def __init__(self, options):
        super().__init__(options)

        # Verify if the input_path was provided
        assert "container_description_path" in options, "The path to the input files should be given as a CLI option as follows: [pybatsim command] -o \'{\"input_path\":\"path/to/input/files\"}\'"
        if not os.path.exists(options["container_description_path"]):
                assert False, "Could not find input path {}".format(options["container_description_path"])

        # Read and save the external profiles (for containers)
        self.list_of_containers = []
        with open(options["container_description_path"]) as f:
            self.container_description = json.load(f)
        for container in self.container_description["profiles"].keys():
            self.list_of_containers.append(container)

        self.nb_completed_jobs = 0
        self.nb_jobs = 0
        self.nb_container_downloaded = 0

        self.notify_already_sent = False
        self.end_of_simulation_asked = False
        
        self.time_next_update = 1.0
        self.update_period = 150
        self.sched_delay = 0.005

        self.jobs_completed = []
        self.jobs_waiting = []
        self.mapping_job_container = {}
        self.mapping_machine_container = {}

        self.scheduling_mapping = {}
        self.availableResources = None
        self.openJobs = set()

        self.global_scheduledJobs = []

        self.container_jobs_scheduled = []
        self.container_jobs_executed = []
        self.original_jobs_scheduled = []

    def downloading_container_as_job(self, job):
        """
        Check if the job is a dynamic job representing a container being downloaded.
        """

        is_container = [s for s in self.list_of_containers if s in job.id]
        if (len(is_container) != 0):
            return is_container[0]
        else:
            return None

    def list_machines_with_container(self, job_container):
        machine_candidates = []
        if(len(self.availableResources) == 0):
            return []
        else:
            for machine in self.availableResources:
                machine_id = int(str(machine))
                if (job_container in self.mapping_machine_container[machine_id]):
                    machine_candidates.append(machine)
            return machine_candidates            

    def onSimulationBegins(self):
        """
        Verify if the correct flags has been set when the simulation begins
        """

        assert self.bs.dynamic_job_registration_enabled, "Registration of dynamic jobs must be enabled for this scheduler to work"
        assert self.bs.ack_of_dynamic_jobs == False, "Acknowledgment of dynamic jobs must be disabled for this scheduler to work"

        self.bs.register_profiles("w0", self.container_description["profiles"])

    def onAfterBatsimInit(self):
        """
        Update the set of Jobs and Resources after the simulation begins
        """

        self.openJobs = set()
        self.availableResources = ProcSet((0,self.bs.nb_compute_resources-1))
        print("Avaliable resources init: ", self.availableResources)
        for availableResource in self.availableResources:
            print("Type: ", type(availableResource))
            self.mapping_machine_container[availableResource] = []
        print("Mapping: ", self.mapping_machine_container)

    def onBeforeEvents(self):
        """
        Update Batsim time with some small delay before new events happen.
        """

        if self.bs.time() >= self.time_next_update:
            self.time_next_update = math.floor(self.bs.time()) + self.update_period

    def scheduleJobs(self):
        """
        The decion process. It will check if the machines have containers required by the jobs.
        If not, dybamic jobs will be created, and these jobs will represent the downloading of containers.
        """

        scheduledJobs = []
        while(len(self.openJobs) > 0):
            job = list(self.openJobs)[0]
            job_container = job.profile_dict['container']['image'] + "_"  + job.profile_dict['container']['tag']

            # Search the best machine available, which means, one with the required container
            machine_candidates = self.list_machines_with_container(job_container)
            if (len(machine_candidates) != 0):
                machine = machine_candidates[0]
            else:
                if(len(self.availableResources) != 0):
                    machine = self.availableResources[0]
                else:
                    break

            # If the container is not on the machine, download it there, before scheduling the job
            if (job_container != None and 
                job_container not in self.mapping_machine_container[machine]):

                # Create a dynamic job
                new_job = self.bs.register_job(
                        job.workload + '!' + job_container + "_job" + str(job.id.split("!")[1]) + "_" + str(self.nb_container_downloaded),
                        1, 
                        2000,
                        job_container, 
                        subtime=None)
                
                self.container_jobs_scheduled.append(new_job)

                # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                new_job.allocation = ProcSet(machine, machine)
                scheduledJobs.append(new_job)

                # Save where job should be executed, and what is the container it depends on
                job.allocation = machine
                self.mapping_job_container[job.id] = [job, new_job.id]
                

                self.nb_jobs += 2
                self.nb_container_downloaded += 1
            
            # Or the container is already in the machine, or the job does not require a container, 
            # so the job can be scheduled
            else:
                self.global_scheduledJobs.append(job)

                # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                job.allocation = ProcSet(machine, machine)
                scheduledJobs.append(job)

                self.nb_jobs += 1
                
            self.availableResources = self.availableResources[1:]
            self.openJobs.remove(job)

            # If all jobs were processed, break the loop to avoid iterating in the first loop for nothing
            if(len(self.availableResources) == 0):
                break

        # Update time
        self.bs.consume_time(self.sched_delay)

        # Send the scheduled jobs to Batsim
        if len(scheduledJobs) > 0:
            self.bs.execute_jobs(scheduledJobs)            


    def onJobSubmission(self, job):
        if (self.downloading_container_as_job(job) == None):
            self.openJobs.add(job)
        self.scheduleJobs()
    
    def onJobCompletion(self, job):
        is_original_job = False
        self.nb_completed_jobs += 1
        self.jobs_completed.append(job)

        # If the completed job is a dynamic job (container), we will use the same machine to compute the original job
        # that required such dynamic job.

        container_name = self.downloading_container_as_job(job)
        if (container_name != None):
            
            # Add the container in the machine
            #for availableResource in self.availableResources:
            machine = int(str(job.allocation))
            if(container_name not in self.mapping_machine_container[machine]):
                self.mapping_machine_container[machine].append(container_name)
            
            # Iterate over the mapping_job_container to find the job related to this dynamic job
            job_related_to_dynamic_job = None
            for map_job_container in self.mapping_job_container.items():
                if(map_job_container[1][1] == job.id):
                    job_related_to_dynamic_job = map_job_container[1][0]

            # If some job is found, send it to be executed.
            if (job_related_to_dynamic_job != None):
                scheduledJobs = [job_related_to_dynamic_job]
                self.bs.execute_jobs(scheduledJobs)
        
        # If it was an original job that was completed, we need to free the machine used
        else:
            # Free the mapping_job_container to not waste memory
            if self.mapping_job_container.get(job.id) != None:
                del self.mapping_job_container[job.id]
            else:
                is_original_job = True

            # Free resources (machines)
            if (len(self.availableResources) == 0):
                if(is_original_job):
                    self.availableResources = job.allocation
                else:
                    self.availableResources = ProcSet((job.allocation, job.allocation))
            else:
                if(is_original_job):
                    self.availableResources += job.allocation
                else:
                    self.availableResources |= ProcSet((job.allocation, job.allocation))

        # Check if the simulation is finished
        if(len(self.openJobs) == 0 and len(self.jobs_completed) == self.bs.nb_jobs_submitted):
            self.bs.notify_registration_finished()
            self.notify_already_sent = True

        if(len(self.openJobs) != 0):
            self.scheduleJobs()