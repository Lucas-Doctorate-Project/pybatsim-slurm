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
            return True
        else:
            return False

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
        for availableResource in self.availableResources:
            self.mapping_machine_container[availableResource] = []

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
        while (len(self.availableResources) > 0 and len(self.openJobs) > 0):
            for job in set(self.openJobs):
                # Get the container name, composed by an image and a tag
                job_container = job.profile_dict['container']['image'] + "_"  + job.profile_dict['container']['tag']
            
                # Get the first machine available
                machine = self.availableResources[0]

                # If the container is not on the machine, download it there, before scheduling the job
                if (not self.downloading_container_as_job(job) and 
                    job_container != None and 
                    job_container not in self.mapping_machine_container[machine]):

                    # Create a dynamic job
                    new_job = self.bs.register_job(
                            job.workload + '!' + job_container + "_f" + str(job.id.split("!")[1]) + "_" + str(self.nb_container_downloaded),
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
                    self.availableResources = self.availableResources[1:]

                    self.nb_jobs += 1
                    self.nb_container_downloaded += 1
                
                self.nb_jobs += 1
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
        if (not self.downloading_container_as_job(job)):
            self.openJobs.add(job)
        self.scheduleJobs()
    
    def onJobCompletion(self, job):
        self.nb_completed_jobs += 1
        self.jobs_completed.append(job)

        # If the completed job is a dynamic job (container), we will use the same machine to compute the original job
        # that required such dynamic job.
        if (self.downloading_container_as_job(job)):
            container_name = job.id.split("!")[1]

            # Iterate over the mapping_job_container to find the job related to this dynamic job
            job_related_to_container = None
            job_id_related_to_container = None
            for map_job_container in self.mapping_job_container.items():
                if(map_job_container[1][1] == job.id):
                    job_related_to_container = map_job_container[1][0]
                    job_id_related_to_container = map_job_container[1][0]

            # If some job is found, send it to be executed.
            if (job_related_to_container != None):
                scheduledJobs = [job_related_to_container]
                self.bs.execute_jobs(scheduledJobs)
        
        # If it was an original job that was completed, we need to free the machine used
        else:
            # Free the mapping_job_container to not waste memory
            if self.mapping_job_container.get(job.id) != None:
                del self.mapping_job_container[job.id]

            # Free resources (machines)
            if (len(self.availableResources) == 0):
                self.availableResources =  ProcSet((job.allocation,job.allocation))
            else:
                self.availableResources = ProcSet(*islice(self.availableResources, len(self.availableResources) + 1))

        # Check if the simulation is finished
        if(len(self.openJobs) == 0 and len(self.jobs_completed) == self.bs.nb_jobs_submitted):
            self.bs.notify_registration_finished()
            self.notify_already_sent = True

        if(len(self.openJobs) != 0):
            self.scheduleJobs()