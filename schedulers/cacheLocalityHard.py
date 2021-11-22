from batsim.batsim import BatsimScheduler, Batsim

import sys
import os
import time
import json
import math
from procset import ProcSet
from itertools import islice


class CacheLocalityHard(BatsimScheduler):

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
        self.mapping_jobs_waiting_machines = {}

        self.scheduling_mapping = {}
        self.availableResources = None
        self.listOfResources = None
        self.openJobs = set()

        #self.global_scheduledJobs = []

        #self.container_jobs_scheduled = []
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

    def get_layers_from_container(self, job_container):
        """
        Get the layers of a job_cotainer and return as a list.
        """

        list_of_layers = self.container_description.get("profiles").get(job_container).get("layers")
        if(list_of_layers != None):
            return list_of_layers
        else:
            return {}

    def get_layers_total_download_size_from_container(self, job_container):
        """
        Get the layers of a job_cotainer and return as a list.
        """

        total_download_size = self.container_description.get("profiles").get(job_container).get("layers_total_download_size")
        if(total_download_size != None):
            return total_download_size
        else:
            return -1

    """
    def list_machines_with_container(self, job_container):
        machine_candidates = []
        for machine in self.listOfResources:
            machine_id = int(str(machine))
            if (job_container in self.mapping_machine_container[machine_id]):
                machine_candidates.append(machine)
        return machine_candidates            
    """
    def list_machines_with_container(self, job_container):
        """
        List machines that already have job_container
        """

        list_of_layers = self.get_layers_from_container(job_container)
        machine_candidates = []
        scores_machine_container = {}
        if(len(self.availableResources) == 0):
            return [], {}
        else:
            # Let's check if any machine available has the job_container
            # or other container with common layers
            for machine in self.availableResources:
                machine_id = int(str(machine))
                scores_machine_container[machine_id] = 0
                containers_in_machine = self.mapping_machine_container[machine_id]
                # It has the job_container
                if (job_container in containers_in_machine):
                    scores_machine_container[machine_id] = 1 #self.get_layers_total_download_size_from_container(job_container)
                    machine_candidates.append(machine)

                # Check other container layers, and compute the percetage of matching
                else:
                    for container in containers_in_machine:
                        list_of_layers_of_second_container = self.get_layers_from_container(container)
                        for layer in list_of_layers:
                            if layer in list_of_layers_of_second_container:
                                scores_machine_container[machine_id] += list_of_layers_of_second_container.get(layer)
                        
                    layers_total_download_size = self.get_layers_total_download_size_from_container(job_container)
                    if(scores_machine_container[machine_id] != 0 and layers_total_download_size != -1):
                        scores_machine_container[machine_id] /= layers_total_download_size
                    
                    # If there is any problem with the container definition, some missing size in the .json file, for example, consider such container as invalid, so size 0
                    else:
                        scores_machine_container[machine_id] = 0

                machine_candidates = sorted(scores_machine_container, key=scores_machine_container.get, reverse=True)
            
            return machine_candidates, scores_machine_container

    def get_earliest_submitted_job(self):
        selected_job = None
        for job in self.openJobs:
            if (selected_job == None):
                selected_job = job
            elif (selected_job.submit_time > job.submit_time):
                selected_job = job
        return selected_job

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
        self.listOfResources = self.availableResources.copy()
        for availableResource in self.availableResources:
            self.mapping_machine_container[availableResource] = []
            self.mapping_jobs_waiting_machines[availableResource] = []

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
            job = self.get_earliest_submitted_job()
            job_container = job.profile_dict['container']['image'] + "_"  + job.profile_dict['container']['tag']

            # Search the best machine available, which means, one with the required container
            download_time_reduction = 0
            machine_candidates, scores_machine_container = self.list_machines_with_container(job_container)
            if (len(machine_candidates) != 0):
                machine = machine_candidates[0]
                download_time_reduction = scores_machine_container[machine]
                machine = ProcSet((machine,machine)) # Convert the machine id to a ProcSet
            
            else:
                if(len(self.availableResources) != 0):
                    machine = ProcSet(*islice(self.availableResources, 1))
                    #self.availableResources -= machine
                else:
                    break

            # If the container is not on the machine, download it there, before scheduling the job
            if (job_container != None and 
                job_container not in self.mapping_machine_container[int(str(machine))]):
                new_profile_name = job_container

                # If there are usefull layers in the allocated machine, create a new profile for such job, with a new delay
                if (download_time_reduction != 0):
                    new_profile_name = job_container + '_reduced_' + str(round(download_time_reduction, 2))
                    new_profile = {}
                    if new_profile_name not in self.container_description["profiles"].keys():
                        new_profile[new_profile_name] = self.container_description["profiles"].get(job_container)
                        new_delay = round(float(new_profile[new_profile_name]["delay"]) * download_time_reduction, 2)
                        new_profile[new_profile_name]["delay"] -= new_delay
                        self.container_description["profiles"][new_profile_name] = new_profile
                        self.bs.register_profiles("w0", new_profile)


                # Create a dynamic job
                new_job = self.bs.register_job(
                        job.workload + '!' + job_container + "_job" + str(job.id.split("!")[1]) + "_" + str(self.nb_container_downloaded),
                        1, 
                        2000,
                        new_profile_name, 
                        subtime=None)
                
                #self.container_jobs_scheduled.append(new_job)

                # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                new_job.allocation = machine
                scheduledJobs.append(new_job)

                # Save where the original job should be executed, and what is the container it depends on
                job.allocation = machine
                self.mapping_job_container[job.id] = [job, new_job.id]

                self.nb_jobs += 2
                self.nb_container_downloaded += 1
            
                self.availableResources -= machine

            # Or the container is already in the machine, or the job does not require a container, 
            # so the job can be scheduled
            else:
                #self.global_scheduledJobs.append(job)

                # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                job.allocation = machine
                if(machine.issubset(self.availableResources) == False) :
                    self.mapping_jobs_waiting_machines[int(str(machine))].append(job)
                else:
                    scheduledJobs.append(job)
                    self.availableResources -= machine

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
        if (self.downloading_container_as_job(job) == None):
            self.openJobs.add(job)
        self.scheduleJobs()
    

    def onJobCompletion(self, job):
        self.nb_completed_jobs += 1
        self.jobs_completed.append(job)
        machine_id = int(str(job.allocation))

        # If the completed job is a dynamic job (container), we will use the same machine to compute the original job
        # that required such dynamic job.
        container_name = self.downloading_container_as_job(job)
        if (container_name != None):
            # Add the container in the machine
            # for availableResource in self.availableResources:
            if(container_name not in self.mapping_machine_container[machine_id]):
                self.mapping_machine_container[machine_id].append(container_name)
            
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

            # Free resources (machines)
            if (len(self.availableResources) == 0):
                self.availableResources = job.allocation
            else:
                self.availableResources |= job.allocation
            
            # Iterate over the mapping_jobs_waiting_machines to search jobs waiting for this machine
            if (len(self.mapping_jobs_waiting_machines[machine_id]) != 0):
                scheduledJobs = [self.mapping_jobs_waiting_machines[machine_id].pop(0)]
                self.availableResources -= job.allocation
                self.bs.execute_jobs(scheduledJobs)

        # Check if the simulation is finished
        if(len(self.openJobs) == 0 and len(self.jobs_completed) == self.bs.nb_jobs_submitted):
            self.bs.notify_registration_finished()
            self.notify_already_sent = True

        if(len(self.openJobs) != 0):
            self.scheduleJobs()