from batsim.batsim import BatsimScheduler, Batsim

import csv
import sys
import os
import time
import json
import math
import random
from procset import ProcSet
from itertools import islice

from approxAlgoLib import *

class ApproxAlgo(BatsimScheduler):

    def __init__(self, options):
        super().__init__(options)
        
        # Verify if the input_path was provided
        #assert "container_description_path" in options, "The path to the input files should be given as a CLI option as follows: [pybatsim command] -o \'{\"input_path\":\"path/to/input/files\"}\'"
        #if not os.path.exists(options["container_description_path"]):
        if "container_description_path" not in options:
            assert False, "Could not find input path {}".format(options)#["container_description_path"])
                
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

        #random.seed(self.random_seed)

        self.nb_completed_jobs = 0
        self.nb_jobs = 0
        self.nb_container_downloaded = 0
        self.total_io_mb = 0
        self.total_container_downloaded_mb = 0
        self.total_container_downloaded_mb_expected = 0

        self.notify_already_sent = False
        self.end_of_simulation_asked = False
        
        self.time_next_update = 1.0
        self.update_period = 150
        self.sched_delay = 0.005

        self.jobs_completed = []
        self.jobs_waiting = []
        self.required_containers = []
        self.list_of_machines = []
        self.machines_description = {}
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

        self.list_of_valid_cost = []
        self.list_of_valid_makespan = []
        self.list_of_cost_max_used = []
        self.list_of_makespan_max_used = []
        self.list_of_cost_lp = []
        self.list_of_makespan_lp = []

# ----------------------------- ApproxAlgo -----------------------------------------

    def callsLPAlgo_example(self):
        print("Example!! ")
        N = 7
        M = 3
        K = 3

        c =    [[3, 1, 1, 1, 1, 1, 1],
                [3, 1, 1, 1, 1, 1, 1],
                [3, 1, 1, 1, 1, 1, 1]]

        p =    [[3, 1, 1, 1, 1, 1, 1],
                [3, 1, 1, 1, 1, 1, 1],
                [3, 1, 1, 1, 1, 1, 1]]

        b =    [[1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 1, 1]]

        d =    [[1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 1, 1]]                

        env =  [0, 0, 0, 0, 0, 0, 0]
        env =  [2, 0, 1, 1, 1, 0, 1]

        Cmax = 12
        Tmax = 4

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
        list_of_containers = []
        list_of_containers_execution_time = []
        list_of_containers_cost = []

        machine_id = 0
        container_id = 0
        #cpu_speed_baseline = self.machines_description[0].split("Mf")[0]

        for machine in list_machines_available:
            function_execution_time_on_machine = []
            functions_cost_on_machine = []
            container_execution_time_on_machine = []
            containers_cost_on_machine = []

            self.mapping_machine_id[machine_id] = machine
            machine_cpu_speed = self.machines_description[machine].split("Mf")[0]
            job_id = 0
            for job in dict_jobs:
                self.mapping_job_id[job_id] = job.id

                function_computation_needed = float(job.profile_dict['cpu'])
                function_execution_time = round((function_computation_needed / float(machine_cpu_speed)) / 1000000, 2)
                if (function_execution_time <= 0 ):
                    function_execution_time = 1
                function_cost = int(job.profile_dict['io'])
                job_container = job.profile_dict['container']['image'] + '_' + job.profile_dict['container']['tag']
                if job_container not in list_of_containers:
                    list_of_containers.append(job_container)

                # Cost is the same for all machines, they are note distubed
                functions_cost_on_machine.append(function_cost)
                function_execution_time_on_machine.append(function_execution_time)
                if(self.mapping_container_id.get(job_container) == None):
                    self.mapping_container_id[job_container] = container_id
                    container_id += 1
                self.mapping_job_container_approx_algo[job.id] = job_container

                job_id += 1

            for job_container in list_of_containers:
                container_computation_needed = float(self.container_description["profiles"][job_container]['cpu'])
                container_execution_time = round((container_computation_needed / float(machine_cpu_speed)) / 1000000, 2)
                if (container_execution_time <= 0 ):
                    container_execution_time = 1
                container_cost = int(self.container_description["profiles"][job_container]['size'])

                # Cost is the same for all machines, they are note distubed
                containers_cost_on_machine.append(container_cost)
                container_execution_time_on_machine.append(container_execution_time)
            
            list_of_functions_execution_time.append(function_execution_time_on_machine)
            list_of_functions_cost.append(functions_cost_on_machine)
            list_of_containers_execution_time.append(container_execution_time_on_machine)
            list_of_containers_cost.append(containers_cost_on_machine)

            machine_id += 1

        list_of_containers = []
        for job in dict_jobs:
            job_container = job.profile_dict['container']['image'] + '_' + job.profile_dict['container']['tag']
            job_container_in_mapping_id = self.mapping_container_id.get(job_container)
            list_of_containers.append(job_container_in_mapping_id)

        return job_id, machine_id, container_id,  list_of_functions_execution_time, list_of_functions_cost, list_of_containers_execution_time, list_of_containers_cost, list_of_containers

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
        
        # Initialize varibles for the LP Algo
        N, M, K, p, c, b, d, env = self.convertBatsimData(dict_jobs, list_machines_available)
        Cmax, Tmax = compute_max_cmax_and_tmax(p, c, b, d, K, M, N)
        #self.verifyConstraintsLPAlgo(Cmax, Tmax, M, N, K, c, p, d, b, env)
        
        # Compute the solution using the safe Cmax and Tmax and save it
        
        # new comments
        #status_basis, x_basis, e_basis = LP(Cmax, Tmax, M, N, K, c, p, d, b, env)
        #status, x, e = status_basis, x_basis, e_basis
        # If there is no solution even with the safe values, finish it
        #if (status == 1):
        #    return 1, None

        # Try to optimize the solution and update the safe results only if there is an optimization available.
        #optimization_factor = self.approx_algo_optimization_factor
        #if (optimization_factor != 0):
        """
        status_new, x_new, e_new, new_cmax, new_tmax, list_of_valid_cmax, list_of_valid_tmax = minimize_cmax_and_tmax(Cmax, Tmax, x_basis, e_basis, M, N, K, c, p, d, b, env)#, optimization_factor)
        if (status_new == 0):
            status, x, e = status_new, x_new, e_new
            Cmax, Tmax = new_cmax, new_tmax
            self.list_of_valid_cost = list_of_valid_cmax
            self.list_of_valid_makespan = list_of_valid_tmax
        """

        status_new, x_new, e_new, new_cmax, new_tmax, list_of_valid_cmax, list_of_valid_tmax, list_of_cmax_used, list_of_tmax_used, list_of_cmax_lp, list_of_tmax_lp = minimize_cmax_and_tmax(Cmax, Tmax, M, N, K, c, p, d, b, env)#, optimization_factor)
        #if (status_new == 0):
        #    status, x, e = status_new, x_new, e_new
        Cmax, Tmax = new_cmax, new_tmax
        self.list_of_valid_cost = list_of_valid_cmax
        self.list_of_valid_makespan = list_of_valid_tmax
        self.list_of_cost_max_used = list_of_cmax_used
        self.list_of_makespan_max_used = list_of_tmax_used
        self.list_of_cost_lp = list_of_cmax_lp
        self.list_of_makespan_lp = list_of_tmax_lp


        print("Input matrixes: ")
        print("c:")
        print_as_matrix(c)
        print("d:")
        print_as_matrix(d)
        print("p:")
        print_as_matrix(p)
        print("b:")
        print_as_matrix(b)

        print("Cmax:",Cmax)
        print("Tmax:",Tmax)

        print("LP solution status : ", status_new)
        #print("Fractional Solution:")
        
        print("Integerized solution : ")
        print_as_matrix(x_new)

        #x_a, e_a = to_integer_solution(x, M, N, K, c, p, d, b, env)

        #print("Integerized solution : ")
        #print_as_matrix(x_a)
        #print(" ------------------------------------------  ")

        return status_new, x_new

    def convertLPSolutionToBatsimFormat(self, lp_solution):
        print("The solution is: \n", lp_solution)

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

# ----------------------------- ApproxAlgo -----------------------------------------
    def save_json_output_as_csv(self, file_name, json_data):
        header = []
        data = []    

        for key,value in json_data.items():
            header.append(key)
            data.append(value)

        with open(file_name, 'w', encoding='UTF8') as f:
            writer = csv.writer(f)
            writer.writerow(header)

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

        list_of_layers = self.get_layers_from_container(job_container)
        machine_candidates = []
        scores_machine_container = {}

        # Let's check if any machine available has the job_container
        # or other container with common layers
        for machine in self.list_of_machines: #self.availableResources:
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
                print(scores_machine_container[machine_id], layers_total_download_size)
                if(scores_machine_container[machine_id] != 0 and layers_total_download_size != -1):
                    print(scores_machine_container[machine_id], layers_total_download_size)
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

    def get_machines_and_speed(self, machines_resource_description):
        for machine in machines_resource_description:
            self.machines_description[machine["id"]] = machine["properties"]["speed"]
        print(self.machines_description)

    def get_machines(self, machines_resource_description):
        for machine in machines_resource_description:
            self.list_of_machines.append(machine["id"])

    def save_output_as_csv(self, file_name, json_data):
        header = []
        data = []    

        for key,value in json_data.items():
            header.append(key)
            data.append(value)

        with open(file_name, 'w', encoding='UTF8') as f:
            writer = csv.writer(f)
            # write the header
            writer.writerow(header)
            # write the data
            writer.writerow(data)
        return

    def onSimulationBegins(self):
        """
        Verify if the correct flags has been set when the simulation begins
        """

        assert self.bs.dynamic_job_registration_enabled, "Registration of dynamic jobs must be enabled for this scheduler to work"
        assert self.bs.ack_of_dynamic_jobs == False, "Acknowledgment of dynamic jobs must be disabled for this scheduler to work"
        
        self.bs.register_profiles("w0", self.container_description["profiles"])
        print("Created new profiles containers at onSimulationBegins: ", self.container_description)

        #print("Calling LP Algo")
        #self.callsLPAlgo_example()

    def onAfterBatsimInit(self):
        """
        Update the set of Jobs and Resources after the simulation begins
        """
        self.openJobs = set()
        self.availableResources = ProcSet((0,self.bs.nb_compute_resources-1))
        for availableResource in self.availableResources:
            self.mapping_machine_container[availableResource] = []
            self.mapping_jobs_waiting_machines[availableResource] = []
        self.get_machines_and_speed(self.bs.machines["compute"])
        self.get_machines(self.bs.machines["compute"])

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
            # Get the allocation decisions
            approx_algo_allocation = None
            if(len(self.openJobs) == self.workload_size):

                solution_status, lp_solution = self.callsLPAlgo(self.openJobs, self.availableResources)
                if (solution_status == 1):
                    break
                approx_algo_allocation = self.convertLPSolutionToBatsimFormat(lp_solution)
            
            if (approx_algo_allocation == None):
                break
            # Since we have the allocation of a set of tasks, per machine, lets allocate the possible ones, 
            # and put the rest in a waiting list.

            # Lets do it per machine
            for machine_id in approx_algo_allocation:
                # per job
                while(len(approx_algo_allocation[machine_id]) > 0):
                    job_id = approx_algo_allocation[machine_id].pop(0)
                    
                    job = None
                    for open_job in self.openJobs:
                        if open_job.id == job_id:
                            job = open_job
                            break

                    # The job is not in OpenJobs anymore, so it should be removed from approx_algo_allocation[machine_id]
                    if job == None:
                        #approx_algo_allocation[machine_id].pop(job_id)
                        break

                    job_io_size = job.profile_dict["io"]
                    job_container = job.profile_dict['container']['image'] + "_"  + job.profile_dict['container']['tag']
                    job_container_size = self.container_description["profiles"][job_container]["size"]

                    # Search the best machine available, which means, one with the required container
                    download_reduction = 0

                    if (job_container not in self.required_containers):
                        self.required_containers.append(job_container)
                    
                    check_layers = True
                    machine_candidates, scores_machine_container = self.list_machines_with_container(job_container, check_layers)
                    if (machine_id in machine_candidates):
                        machine = machine_id
                        download_reduction = scores_machine_container[machine]
                    else:
                        break

                    machine = ProcSet((machine_id,machine_id)) # Convert the machine id to a ProcSet
                    # If the container is not on the machine, download it there, before scheduling the job
                    if (job_container != None and 
                        job_container not in self.mapping_machine_container[int(str(machine))]):
                        self.total_container_downloaded_mb_expected += job_container_size

                        new_profile_name = job_container
                        new_size = job_container_size
                        # If there are usefull layers in the allocated machine, create a new profile for such job, with a new delay
                        if (download_reduction != 0):
                            new_profile_name = job_container + '_reduced_' + str(round(download_reduction, 2))
                            new_profile = {}
                            if new_profile_name not in self.container_description["profiles"].keys():
                                new_profile[new_profile_name] = self.container_description["profiles"].get(job_container)
                        
                                if (download_reduction >= 1):
                                    new_computation_required = 1
                                    new_size = 1
                                    
                                else:
                                    new_computation_required = round(new_profile[new_profile_name]["cpu"] - (new_profile[new_profile_name]["cpu"] * download_reduction), 2)
                                    new_size = round(new_profile[new_profile_name]["size"] - (new_profile[new_profile_name]["size"] * download_reduction), 2)

                                new_profile[new_profile_name]["cpu"] = new_computation_required
                                new_profile[new_profile_name]["size"] = new_size
                                
                                self.container_description["profiles"][new_profile_name] = new_profile
                                print("Registering new profile: ", new_profile)
                                self.bs.register_profiles("w0", new_profile)

                        # Create a dynamic job
                        new_job = self.bs.register_job(
                                job.workload + '!' + job_container + "_job" + str(job.id.split("!")[1]) + "_" + str(self.nb_container_downloaded),
                                1, 
                                2000,
                                new_profile_name, 
                                subtime=None)
                    
                        self.container_jobs_scheduled.append(new_job)
                        self.total_container_downloaded_mb += new_size
                        
                        # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                        new_job.allocation = machine

                        # Check if the machine is available, if not, put in a waiting list
                        if(machine.issubset(self.availableResources) == True):
                            # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                            scheduledJobs.append(new_job)
                            self.nb_jobs += 2
                            self.nb_container_downloaded += 1
                            self.availableResources -= machine

                        else:
                            self.mapping_jobs_waiting_machines[int(str(machine))].append(new_job)

                        # Save where job should be executed, and what is the container it depends on
                        job.allocation = machine
                        self.mapping_job_container[job.id] = [job, new_job.id]
                        
                        # Add the container as it is already executed in the machine.
                        # Then other jobs can see it and plan to be in the same machine
                        container_name = self.downloading_container_as_job(new_job)
                        self.mapping_machine_container[machine_id].append(container_name)
                
                    # Or the container is already in the machine, or the job does not require a container, 
                    # so the job can be scheduled
                    else:
                        job.allocation = machine
                        if(machine.issubset(self.availableResources) == False) :
                            self.mapping_jobs_waiting_machines[int(str(machine))].append(job)
                        else:
                            scheduledJobs.append(job)
                            self.availableResources -= machine

                        # Allocate the new job to the machine reserved, and add it in the scheduledJobs list
                        self.nb_jobs += 1

                    self.openJobs.remove(job)
                    self.total_io_mb += job_io_size
                self.availableResources -= machine

            # If all jobs were processed, break the loop to avoid iterating in the first loop for nothing
            #if(len(self.availableResources) == 0):
            #    break

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

            header = ["valid_cost", "valid_makespan", "max_cost_used", "max_makespan_used", "max_cost_lp", "max_makespan_lp"]
            with open(self.download_info_csv_path + "out_valid_solutions.csv", 'w', encoding='UTF8') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                for i in range(0, len(self.list_of_valid_cost)):
                    row = [self.list_of_valid_cost[i], self.list_of_valid_makespan[i], self.list_of_cost_max_used[i], self.list_of_makespan_max_used[i], self.list_of_cost_lp[i], self.list_of_makespan_lp[i]]
                    writer.writerow(row)