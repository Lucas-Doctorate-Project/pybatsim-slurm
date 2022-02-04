from pickle import FALSE
from batsim.batsim import BatsimScheduler, Batsim

import csv
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
        #assert "container_description_path" in options, "The path to the input files should be given as a CLI option as follows: [pybatsim command] -o \'{\"input_path\":\"path/to/input/files\"}\'"
        #if not os.path.exists(options["container_description_path"]):
        if "container_description_path" not in options:
           assert False, "Could not find input path {}".format(options["container_description_path"])
                
        if "download_info_csv_path" in options:
            self.download_info_csv_path = options["download_info_csv_path"]
        else:
            assert False, "Could not find input path {}".format(options["download_info_csv_path"])

        if "workload_size" in options:
            self.workload_size = options["workload_size"]
        else:
            assert False, "Could not find input path {}".format(options["workload_size"])

        if "random_seed" in options:
            self.random_seed = options["random_seed"]
        else:
            assert False, "Could not find input path {}".format(options["random_seed"])

        # Read and save the external profiles (for containers)
        self.list_of_containers = []
        with open(options["container_description_path"]) as f:
            self.container_description = json.load(f)
        for container in self.container_description["profiles"].keys():
            self.list_of_containers.append(container)

        self.nb_completed_jobs = 0
        self.nb_jobs = 0
        self.nb_container_downloaded = 0
        self.total_container_downloaded_mb = 0
        self.total_container_downloaded_mb_expected = 0
        self.total_io_mb = 0

        self.notify_already_sent = False
        self.end_of_simulation_asked = False
        
        self.time_next_update = 1.0
        self.update_period = 150
        self.sched_delay = 0.005

        self.jobs_completed = []
        self.jobs_waiting = []
        self.required_containers = []
        self.mapping_job_container = {}
        self.mapping_machine_container = {}

        self.scheduling_mapping = {}
        self.availableResources = None
        self.openJobs = set()

        self.global_scheduledJobs = []

        self.container_jobs_scheduled = []
        self.container_jobs_executed = []
        self.original_jobs_scheduled = []

    def save_output_as_csv(self, file_name, json_data):
        print("Saving output")
        header = []
        data = []    

        for key,value in json_data.items():
            header.append(key)
            data.append(value)

        print(header, data)

        with open(file_name, 'w', encoding='UTF8') as f:
            writer = csv.writer(f)

            # write the header
            writer.writerow(header)
            # write the data
            writer.writerow(data)
        return

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

        total_download_size = self.container_description.get("profiles").get(job_container).get("size")
        if(total_download_size != None):
            return total_download_size
        else:
            return -1

    def list_machines_with_container(self, job_container, check_layers=False):
        """
        List machines that already have job_container
        """

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
                if(check_layers and job_container not in containers_in_machine):
                    list_of_layers = self.get_layers_from_container(job_container)
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

        while(len(self.openJobs) != self.workload_size):
            break
        scheduledJobs = []
        while(len(self.openJobs) > 0):
            job = self.get_earliest_submitted_job()
            #print("job.profile_dict:", job)
            job_io_size = job.profile_dict["io"]
            job_container = job.profile_dict['container']['image'] + "_"  + job.profile_dict['container']['tag']
            job_container_size = self.container_description["profiles"][job_container]["size"]
            
            # Search the best machine available, which means, one with the required container
            download_reduction = 0

            if (job_container not in self.required_containers):
                self.required_containers.append(job_container)           
            
            check_layers = True
            machine_candidates, scores_machine_container = self.list_machines_with_container(job_container, check_layers)
            if (len(machine_candidates) != 0):
                machine = machine_candidates[0]
                download_reduction = scores_machine_container[machine]
                print("download_reduction: ", download_reduction)
                machine = ProcSet((machine,machine)) # Convert the machine id to a ProcSet
            else:
                if(len(self.availableResources) != 0):
                    machine = ProcSet(*islice(self.availableResources, 1))
                else:
                    break

            # If the container is not on the machine, download it there, before scheduling the job
            if (job_container != None and 
                job_container not in self.mapping_machine_container[int(str(machine))]):
                print("Job container: ", job_container)
                self.total_container_downloaded_mb_expected += job_container_size
                new_profile_name = job_container
                new_size = job_container_size
                # If there are usefull layers in the allocated machine, create a new profile for such job, with a new delay
                if (download_reduction != 0):
                    new_profile_name = job_container + '_reduced_' + str(round(download_reduction, 2))
                    new_profile = {}
                    if new_profile_name not in self.container_description["profiles"].keys():
                        new_profile[new_profile_name] = self.container_description["profiles"].get(job_container)
                        
                        new_computation_required = round(new_profile[new_profile_name]["cpu"] - (new_profile[new_profile_name]["cpu"] * download_reduction), 2)
                        print("new_computation_required: ", new_computation_required, new_profile[new_profile_name]["cpu"])
                        new_profile[new_profile_name]["cpu"] = new_computation_required
                        
                        new_size = round(new_profile[new_profile_name]["size"] - (new_profile[new_profile_name]["size"] * download_reduction), 2)
                        print("new_size: ", new_size, new_profile[new_profile_name]["size"])
                        new_profile[new_profile_name]["size"] = new_size
                        
                        self.container_description["profiles"][new_profile_name] = new_profile
                        self.bs.register_profiles("w0", new_profile)

                # Create a dynamic job
                new_job = self.bs.register_job(
                    job.workload + '!' + job_container + "_job" + str(job.id.split("!")[1]) + "_" + str(self.nb_container_downloaded),
                    1, 
                    18000,
                    new_profile_name, 
                    subtime=None)
                
                self.container_jobs_scheduled.append(new_job)
                print("There is new size here", new_size)
                self.total_container_downloaded_mb += new_size

                # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                new_job.allocation = machine
                scheduledJobs.append(new_job)

                # Save where job should be executed, and what is the container it depends on
                job.allocation = machine
                self.mapping_job_container[job.id] = [job, new_job.id]
                
                self.nb_jobs += 2
                self.nb_container_downloaded += 1

                # Add the container in the machine
                # for availableResource in self.availableResources:
                self.mapping_machine_container[int(str(machine))].append(job_container)
            
            # Or the container is already in the machine, or the job does not require a container, 
            # so the job can be scheduled
            else:
                self.global_scheduledJobs.append(job)

                # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                job.allocation = machine
                scheduledJobs.append(job)

                self.nb_jobs += 1

            self.total_io_mb += job_io_size
            self.availableResources -= machine
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

        # If the completed job is a dynamic job (container), we will use the same machine to compute the original job
        # that required such dynamic job.
        container_name = self.downloading_container_as_job(job)
        if (container_name != None):
            
            # Add the container in the machine
            # for availableResource in self.availableResources:
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

            # Free resources (machines)
            if (len(self.availableResources) == 0):
                self.availableResources = job.allocation
            else:
                self.availableResources |= job.allocation 
        
        """
        print("Heeeeeeere")
        print("self.openJobs", self.openJobs)
        print("self.jobs_completed", self.jobs_completed)
        print("self.bs.nb_jobs_submitted", self.bs.nb_jobs_submitted)
        # Check if the simulation is finished
        if(len(self.openJobs) == 0 and len(self.jobs_completed) == self.bs.nb_jobs_submitted and self.notify_already_sent == False):

            print("Notified finished")
            self.bs.notify_registration_finished()
            self.notify_already_sent = True
        """
        if(len(self.openJobs) != 0):
            self.scheduleJobs()

    def onNoMoreEvents(self):
        if(self.bs.nb_jobs_submitted != 0 and len(self.openJobs) == 0 and len(self.jobs_completed) == self.bs.nb_jobs_submitted and self.notify_already_sent == False):
            self.notify_already_sent = True
            self.bs.notify_registration_finished()

            output_data = {
                "total_io": self.total_io_mb,
                "total_container_data_downloaded_mb_expected": self.total_container_downloaded_mb_expected,
                "total_container_data_downloaded_mb": self.total_container_downloaded_mb, 
                "nb_different_required_containers": len(self.required_containers),
                "nb_container_downloaded": self.nb_container_downloaded,
                "total_io_and_container_data_downloaded": self.total_io_mb + self.total_container_downloaded_mb
            }
            self.save_output_as_csv(self.download_info_csv_path + "out_download_data_info.csv", output_data)
