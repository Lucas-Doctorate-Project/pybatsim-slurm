from batsim.batsim import BatsimScheduler, Batsim

import sys
import os
import time
import json
import math
from procset import ProcSet
from itertools import islice


class FillerSched(BatsimScheduler):

    def __init__(self, options):
        super().__init__(options)
        self.nb_completed_jobs = 0
        self.nb_jobs = 0

        self.nb_container_downloaded = 0
        self.notify_already_send = False
        self.end_of_simulation_asked = False
        self.time_next_update = 1.0
        self.update_period = 150
        self.jobs_completed = []
        self.jobs_waiting = []

        self.sched_delay = 0.005
        self.availableResources = None
        self.openJobs = set()
        self.container_mapping = {}

    def onAfterBatsimInit(self):
        # It is a set of type 'batsim.batsim.Job'
        self.openJobs = set()
        print("Criou Open Jobs: ", self.openJobs, len(self.openJobs))
        self.availableResources = ProcSet((0,self.bs.nb_compute_resources-1))
        print("available resources: ", self.availableResources)
        for availableResource in self.availableResources:
            print("available resource: ", availableResource, type(availableResource))
            self.container_mapping[availableResource] = []
        print("Initial mapping: ", self.container_mapping)

    def onBeforeEvents(self):
        if self.bs.time() >= self.time_next_update:
            self.time_next_update = math.floor(self.bs.time()) + self.update_period

    def scheduleJobs(self):
        scheduledJobs = []
        #self.nb_jobs += len(self.openJobs)
        print('nbJobs = ', len(self.openJobs), self.nb_jobs)
        print('nbJobsBatsim = ', self.bs.nb_jobs_submitted, self.bs.nb_jobs_submitted_from_scheduler, self.bs.nb_jobs_submitted_from_batsim)

        print('openJobs = ', self.openJobs)
        print('available = ', self.availableResources)

        # Iterating over a copy to be able to remove jobs from openJobs at traversal
        print("Let's look each job")
        # Each job looks like: 
        # {Job w0!9; sub:27 res:1 reqtime:100 prof:delay10 state:State.SUBMITTED ret:None alloc:None, meta:None}
        for job in set(self.openJobs):
            print("#@@@@@@@@@@ ", job.workload)
            print(self.container_mapping)
            job_container = job.profile_dict['container']
            print("olha ai ", job, type(job), job.profile, job.profile_dict, job.json_dict, job_container)
            
            nb_res_req = job.requested_resources
            if nb_res_req <= len(self.availableResources):
                # Retrieve the *nb_res_req* first availables resources
                job_alloc = ProcSet(*islice(self.availableResources, nb_res_req))
                job.allocation = job_alloc

                print("Resources chosen: ", job.allocation, type(job.allocation))
                for resource_allocated in job.allocation:
                    print("Tem algo aqui?: ", self.container_mapping[resource_allocated])
                    if (job_container not in self.container_mapping[resource_allocated]):
                        print("Creating Dynamic Job")
                        self.bs.register_job(
                            job.workload + '!' + job_container + "_" + str(self.nb_container_downloaded),
                            1, 
                            600,
                            job.profile, 
                            subtime=None)
                        self.nb_jobs += 1
                        print("Mandou agora: ", job.workload + '!' + job_container + "_" + str(self.nb_container_downloaded))
                        print("resource: ", resource_allocated, type(resource_allocated))
                        self.container_mapping[resource_allocated].append(job.profile_dict['container'])
                        self.nb_container_downloaded += 1
                    print("E agora?: ", self.container_mapping[resource_allocated])
                scheduledJobs.append(job)

                self.availableResources -= job_alloc

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
            self.scheduleJobs()
    
    def onJobCompletiozn(self, job):
        print("Completed: ", job)
        
        self.availableResources |= job.allocation
        self.nb_completed_jobs += 1
        self.jobs_completed.append(job)

        print('check if finished', self.openJobs, len(self.openJobs))
        print('check if finished', self.jobs_completed, len(self.jobs_completed), self.bs.nb_jobs_submitted)
        
        if(len(self.openJobs) == 0 and len(self.jobs_completed) == self.bs.nb_jobs_submitted):
            print("Tell that it is finished !")
            self.bs.notify_registration_finished()
            self.notify_already_send = True

        print('primeiro if', len(self.openJobs) == 0)
        print('segundo if', len(self.jobs_completed) == self.bs.nb_jobs_submitted)

        if(len(self.openJobs) != 0):
            print("Finished to look to openJobs")
            self.scheduleJobs()

        print("Aqui ", self.jobs_completed, self.bs.nb_jobs_submitted)
        if(len(self.jobs_completed) != self.bs.nb_jobs_submitted):
            print("Not finished, wait ;) ", time.time() + 10)
            #time.sleep(10)
            self.bs.wake_me_up_at(self.bs.time() + 100)
            #self.bs.do_next_event()
            #self.scheduleJobs()

    """
    def onJobCompletion(self, job):
        print("Completed: ", job)
        
        self.availableResources |= job.allocation
        self.nb_completed_jobs += 1
        self.jobs_completed.append(job)

   
    def onNoMoreEvents(self):
        print("No more !!")           
        print('check if finished', self.openJobs, len(self.openJobs))
        print('check if finished', self.jobs_completed, len(self.jobs_completed), self.bs.nb_jobs_submitted)
        
        if(len(self.openJobs) == 0) and (len(self.jobs_completed) == self.bs.nb_jobs_submitted) and (self.bs.nb_jobs_submitted != 0): 
            print("Tell that it is finished !")
            self.bs.notify_registration_finished()
            
            #self.notify_already_send = True

        print('primeiro if', len(self.openJobs) == 0)
        print('segundo if', len(self.jobs_completed) == self.bs.nb_jobs_submitted)

        if(len(self.openJobs) != 0):
            print("Continue escalonando")
            self.scheduleJobs()

        print("Aqui ", self.jobs_completed, self.bs.nb_jobs_submitted)
        if(len(self.jobs_completed) != self.bs.nb_jobs_submitted):
            print("Not finished, wait ;) ", time.time() + 10)
            print("Batsim time: ", self.bs.time)
            self.bs.wake_me_up_at(self.time_next_update)

    """