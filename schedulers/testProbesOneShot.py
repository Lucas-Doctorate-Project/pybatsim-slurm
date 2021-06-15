from batsim.batsim import BatsimScheduler, Batsim

import sys
import os
from procset import ProcSet
from itertools import islice


class TestProbesOneShot (BatsimScheduler):

    def onAfterBatsimInit(self):
        self.nb_completed_jobs = 0

        self.jobs_completed = []
        self.jobs_waiting = []

        self.sched_delay = 0.005

        self.openJobs = set()
        self.availableResources = ProcSet((0,self.bs.nb_compute_resources-1))
        


    def scheduleJobs(self):
        scheduledJobs = []
        print('openJobs = ', self.openJobs)
        print('available = ', self.availableResources)
        job = None
        if len(set(self.openJobs)) >0 :
            job =set(self.openJobs).pop()
        if(job !=None):
            nb_res_req = job.requested_resources
            if nb_res_req <= len(self.availableResources):
             # Retrieve the *nb_res_req* first availables resources
                job_alloc = ProcSet(*islice(self.availableResources, nb_res_req))
                job.allocation = job_alloc
                scheduledJobs.append(job)

                self.availableResources -= job_alloc

                self.openJobs.remove(job)
            else :
                self.openJobs.add(job)


        # update time
        self.bs.consume_time(self.sched_delay)

        # send to uds
        if len(scheduledJobs) > 0:
            self.bs.execute_jobs(scheduledJobs)

        print('openJobs = ', self.openJobs)
        print('available = ', self.availableResources)
        print('')



        

    def onJobSubmission(self, job):
        self.bs.add_probe('myprobe','true','maximum', '1-3','power consumption')
        self.bs.add_probe('myprobe','true','maximum', '1-3','energy consumed')
        self.bs.add_probe('myprobe','true','maximum', '1-3','average load')
        self.bs.add_probe('myprobe','true','maximum', '1-3','current load')

        # self.bs.add_probe('myprobe','false','none','1-3','power consumption')
        # self.bs.add_probe('myprobe','false','none', '1-3','power consumption')
        if job.requested_resources > self.bs.nb_compute_resources:
            self.bs.reject_jobs([job]) 
        else:
            self.openJobs.add(job)
            self.scheduleJobs()

    def onJobCompletion(self, job):
        # self.bs.add_probe('myprobe','true','addition', '1-3','current load')
        # self.bs.add_probe('myprobe','true','addition','1-3','average load')
        # self.bs.add_probe('myprobe','false','none','1-3','current load')
        # self.bs.add_probe('myprobe','false','none', '1-3','average load')
        self.availableResources |= job.allocation
        self.scheduleJobs()

