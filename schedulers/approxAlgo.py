from batsim.batsim import BatsimScheduler, Batsim

import sys
import os
import time
import json
import math
from procset import ProcSet
from itertools import islice

from approxAlgoLib import *

class ApproxAlgo(BatsimScheduler):

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

        self.mapping_job_container_approx_algo = {} # To be used with the Approx Algo.
        self.mapping_job_id = {}
        self.mapping_machine_id = {}
        self.mapping_container_id = {}
        self.mapping_container_job = {}

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

    def callsLPAlgo_example(self):
        print("Here")
        N = 7
        M = 3
        K = 1

        c =    [[3, 1, 1, 1, 1, 1, 1],
                [3, 1, 1, 1, 1, 1, 1],
                [3, 1, 1, 1, 1, 1, 1]]

        p =    [[3, 1, 1, 1, 1, 1, 1],
                [3, 1, 1, 1, 1, 1, 1],
                [3, 1, 1, 1, 1, 1, 1]]

        d =    [[0, 0],
                [0, 0],
                [0, 0]]

        b =    [[0, 0],
                [0, 0],
                [0, 0]]

        env =  [0, 0, 0, 0, 0, 0, 0]

        Cmax = 9
        Tmax = 3

        print(type(c), type(Cmax))

        status, x, e = LP(Cmax, Tmax, M, N, K, c, p, d, b, env)
        print("LP solution : ")
        print(str(np.round(x, 2)))

        print("Converting to integer")
        print(N)
        print(M)
        print(K)
        print(c)
        print(p)
        print(d)
        print(b)
        print(env)
        print(Cmax)
        print(Tmax)

        x_a, e_a = to_integer_solution(x, M, N, K, c, p, d, b, env)

        print("Integerized solution : ")
        print(x_a)

    def convertBatsimData(self, dict_jobs, list_machines_available):
        print(" --------------- convertBatsimData ---------------------------  ")
        list_of_functions_execution_time = []
        list_of_functions_cost = []

        list_of_containers_execution_time = []
        list_of_containers_cost = []

        machine_id = 0
        container_id = 0

        for machine in list_machines_available:
            function_execution_time_on_machine = []
            functions_cost_on_machine = []
            container_execution_time_on_machine = []
            containers_cost_on_machine = []
            self.mapping_machine_id[machine_id] = machine
            
            job_id = 0
            
            mapping_container_job = []
            for job in dict_jobs:
                self.mapping_job_id[job_id] = job.id

                function_execution_time = int(job.profile_dict['delay'])
                function_execution_time_on_machine.append(function_execution_time)

                function_cost = int(job.profile_dict['bw'])
                functions_cost_on_machine.append(function_cost)

                job_container = job.profile_dict['container']['image'] + '_' + job.profile_dict['container']['tag']
                container_execution_time = int(self.container_description["profiles"][job_container]['delay'])
                container_execution_time_on_machine.append(container_execution_time)

                container_cost = int(self.container_description["profiles"][job_container]['bw'])
                containers_cost_on_machine.append(container_cost)

                if(self.mapping_container_id.get(job_container) == None):
                    self.mapping_container_id[container_id + len(self.mapping_container_id)] = job_container
                self.mapping_job_container_approx_algo[job.id] = job_container

                job_id += 1

            list_of_functions_execution_time.append(function_execution_time_on_machine)
            list_of_functions_cost.append(functions_cost_on_machine)
            list_of_containers_execution_time.append(container_execution_time_on_machine)
            list_of_containers_cost.append(containers_cost_on_machine)

            machine_id += 1

        job_id = 0
        list_of_containers = []
        for job in dict_jobs:
            job_container = job.profile_dict['container']['image'] + '_' + job.profile_dict['container']['tag']
            job_container_in_mapping_id = self.mapping_container_id.get(job_container)
            list_of_containers.append(job_container_in_mapping_id)

        print(list_of_containers)
        
        print("List of list_of_functions_execution_time", list_of_functions_execution_time)
        print("List of list_of_functions_cost", list_of_functions_cost)
        print("List of list_of_containers_execution_time", list_of_containers_execution_time)
        print("List of list_of_containers_cost", list_of_containers_cost)
        print("List of list_of_containers_jobs", list_of_containers)

        print("mapping_machine_id ", self.mapping_machine_id)
        print("mapping_job_id ", self.mapping_job_id)
        print("mapping_container_id ", self.mapping_container_id)
        print("mapping_container_job ", self.mapping_container_job)
        print("mapping_container_id ", self.mapping_container_id)
        print(" ------------------------------------------  ")

        return list_of_functions_execution_time, list_of_functions_cost, list_of_containers_execution_time, list_of_containers_cost, list_of_containers

    """
    def verifyConstraintsLPAlgo(self, Cmax, Tmax, M, N, K, c, p, d, b, env):
        sum_cx = 0
        for line in range(0, len(c)):
            for column in range(0, len(c[line])):
                sum_cx += c[line][column] + x[line][column]
        print("sum_cx", sum_cx)
    """

    def callsLPAlgo(self, dict_jobs, list_machines_available):
        print(" ------------------------- callsLPAlgo -------------------- ")
        p, c, b, d, env = self.convertBatsimData(dict_jobs, list_machines_available)
        print("p,c,b,d, env: ", p, c, b, d, env)
        env =  [0, 0, 0, 0, 0, 0, 0]
        N = 7
        M = 3
        K = 1
        Cmax = 9
        Tmax = 3
        
        #self.verifyConstraintsLPAlgo(Cmax, Tmax, M, N, K, c, p, d, b, env)
        
        status, x, e = LP(Cmax, Tmax, M, N, K, c, p, d, b, env)
        print("LP solution : ", status)
        print("Solution e: ", e)
        print(str(np.round(x, 2)))

        print("Converting to integer")
        print(N)
        print(M)
        print(K)
        print(c)
        print(p)
        print(d)
        print(b)
        print(env)
        print(Cmax)
        print(Tmax)
        x_a, e_a = to_integer_solution(x, M, N, K, c, p, d, b, env)

        print("Integerized solution : ")
        print(x_a)
        print(" ------------------------------------------  ")

        return x_a

    def convertLPSolutionToBatsimFormat(self, lp_solution):
        print("The solution is: ", lp_solution)

        allocation_dict = {}
        for machine_id in range(0, len(lp_solution)):
            for job_id in range(0, len(lp_solution[machine_id])):
                if (lp_solution[machine_id][job_id] == 1):
                    machine = self.mapping_machine_id[machine_id]
                    job = self.mapping_job_id[job_id]
                    if(allocation_dict.get(machine) == None):
                        allocation_dict[machine] = [job]
                    else:
                        allocation_dict[machine].append(job)

        print("The allocation dict is: ", allocation_dict)
        return allocation_dict

    def onSimulationBegins(self):
        """
        Verify if the correct flags has been set when the simulation begins
        """

        assert self.bs.dynamic_job_registration_enabled, "Registration of dynamic jobs must be enabled for this scheduler to work"
        assert self.bs.ack_of_dynamic_jobs == False, "Acknowledgment of dynamic jobs must be disabled for this scheduler to work"
        
        #self.bs.register_profiles("w0", self.container_description["profiles"])
        #print("Created new profiles containers at onSimulationBegins: ", self.container_description)

        #print("Calling LP Algo")
        #self.callsLPAlgo_example()

    def onAfterBatsimInit(self):
        """
        Update the set of Jobs and Resources after the simulation begins
        """
        print("Inited")
        self.openJobs = set()
        self.availableResources = ProcSet((0,self.bs.nb_compute_resources-1))
        for availableResource in self.availableResources:
            self.mapping_machine_container[availableResource] = []
            self.mapping_jobs_waiting_machines[availableResource] = []

    def onBeforeEvents(self):
        """
        Update Batsim time with some small delay before new events happen.
        """
        print("Before events")
        if self.bs.time() >= self.time_next_update:
            self.time_next_update = math.floor(self.bs.time()) + self.update_period

    def scheduleJobs(self):
        """
        The decion process. It will check if the machines have containers required by the jobs.
        If not, dybamic jobs will be created, and these jobs will represent the downloading of containers.
        """
        print("Scheduling: ", self.openJobs)
        scheduledJobs = []
        #self.convertOpenJobsToCostMatrix(self.openJobs, self.availableResources)
        
        # Get the allocation decisions
        approx_algo_allocation = None 
        allocation_decisions = None
        if(len(self.openJobs) == 7):
            print("Time to call LP")
            lp_solution = self.callsLPAlgo(self.openJobs, self.availableResources)
            approx_algo_allocation = self.convertLPSolutionToBatsimFormat(lp_solution)
            print("approx_algo_allocation", approx_algo_allocation)
        if (approx_algo_allocation != None):
            allocation_decisions = approx_algo_allocation.copy()

            for machine in allocation_decisions:
                # Get machine and job_id
                print("machine", machine)
                for job_id in allocation_decisions[machine]:
                    job = None
                    for open_job in self.openJobs:
                        if open_job.id == job_id:
                            job = open_job
                            break

                    # Or the job is no on OpenJobs anymore, or it is a container that need to be downloaded
                    if job != None:
                        # TODO To implement here the dynamic jobs
                        #if (is_container())
                        job.allocation = ProcSet(machine,machine)
                        self.mapping_jobs_waiting_machines[int(str(machine))].append(job)
            print("Machines waiting", self.mapping_jobs_waiting_machines)

        while(approx_algo_allocation != None and len(self.openJobs) > 0):
            for machine in self.availableResources:
                jobs_for_machine = self.mapping_jobs_waiting_machines[machine]
                print("jobs_for_machine", jobs_for_machine)
                if (len(jobs_for_machine) > 0):
                    job = jobs_for_machine.pop(0)
                    print("Selected machine", machine)
                    print("Selected job", job)
                    self.global_scheduledJobs.append(job)

                    # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                    machine = ProcSet((machine,machine))
                    job.allocation = machine
                    scheduledJobs.append(job)

                    self.nb_jobs += 1
    
                    self.availableResources -= machine
                    self.openJobs.remove(job)
            
            # If all jobs were processed, break the loop to avoid iterating in the first loop for nothing
            if(len(self.availableResources) == 0):
                break
                
        print("Here!!")

        # Update time
        self.bs.consume_time(self.sched_delay)

        # Send the scheduled jobs to Batsim
        if len(scheduledJobs) > 0:
            print("Sent to schedule", scheduledJobs)
            self.bs.execute_jobs(scheduledJobs)

        """
        # Submitt one job per machine
        while(approx_algo_allocation != None and len(self.openJobs) > 0):
            for machine in allocation_decisions:
                # Check if the machine is available. It will be not if it is still executing the last allocated job
                print("Available", self.availableResources)
                print(machine in self.availableResources)
                if machine not in self.availableResources:
                    break

                # Get machine and job_id
                print("machine", machine)
                if (len(allocation_decisions[machine]) > 0):
                    job_id = allocation_decisions[machine].pop(0)
                print("job", job_id)

                # Retrieve the full job description in OpenJobs
                job = None
                for open_job in self.openJobs:
                    if open_job.id == job_id:
                        job = open_job
                        break

                # If we found the job succesfully, we submitt it
                if job != None:
                    print("Selected job", job)
                    
                    self.global_scheduledJobs.append(job)

                    # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                    machine = ProcSet((machine,machine))
                    job.allocation = machine
                    scheduledJobs.append(job)

                    self.nb_jobs += 1
    
                    self.availableResources -= machine
                    self.openJobs.remove(job)

            # If all jobs were processed, break the loop to avoid iterating in the first loop for nothing
            if(len(self.availableResources) == 0):
                break
                
        print("Here!!")

        # Update time
        self.bs.consume_time(self.sched_delay)

        # Send the scheduled jobs to Batsim
        if len(scheduledJobs) > 0:
            print("Sent to schedule", scheduledJobs)
            self.bs.execute_jobs(scheduledJobs)
        """
        """
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
                
                self.container_jobs_scheduled.append(new_job)

                # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                new_job.allocation = machine
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
                job.allocation = machine
                scheduledJobs.append(job)

                self.nb_jobs += 1
  
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

        """
    def onJobSubmission(self, job):
        print("Submitted", job)
        if (self.downloading_container_as_job(job) == None):
            self.openJobs.add(job)
        self.scheduleJobs()
    

    def onJobCompletion(self, job):
        print("Job completion", job)
        self.nb_completed_jobs += 1
        self.jobs_completed.append(job)
        machine_id = int(str(job.allocation))

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
            
            # Iterate over the mapping_jobs_waiting_machines to search jobs waiting for this machine
            if (len(self.mapping_jobs_waiting_machines[machine_id]) != 0):
                print("There are jobs waiting for this machine: ", self.mapping_jobs_waiting_machines[machine_id])
                scheduledJobs = [self.mapping_jobs_waiting_machines[machine_id].pop(0)]
                self.availableResources -= job.allocation
                self.bs.execute_jobs(scheduledJobs)
                self.openJobs.remove(scheduledJobs[0])

        # Check if the simulation is finished
        print("Verifying to finish", self.openJobs, self.jobs_completed, self.bs.nb_jobs_submitted)
        if(len(self.openJobs) == 0 and len(self.jobs_completed) == self.bs.nb_jobs_submitted):
            self.bs.notify_registration_finished()
            self.notify_already_sent = True

        if(len(self.openJobs) != 0):
            self.scheduleJobs()