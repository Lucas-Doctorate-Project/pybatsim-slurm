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
        self.probe = True
        


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
        # self.bs.add_hosts_probe('myprobe','none', '1-3','power consumption')
        if job.requested_resources > self.bs.nb_compute_resources:
            self.bs.reject_jobs([job]) 
        else:
            self.openJobs.add(job)
            self.scheduleJobs()
        if(self.probe):
            self.probe = False
            self.bs.add_hosts_probe_one_shot('myprobe1','none', '1-3','energy consumed')
            self.bs.add_hosts_probe_one_shot('myprobe2','none', '1-3','power consumption')
            self.bs.add_hosts_probe_one_shot('myprobe3','none', '1-3','current load')
            self.bs.add_hosts_probe_one_shot('myprobe4','none', '1-3','average load')
            self.bs.add_hosts_probe_one_shot('myprobe5','minimum', '1-3','energy consumed')
            self.bs.add_hosts_probe_one_shot('myprobe6','minimum', '1-3','power consumption')
            self.bs.add_hosts_probe_one_shot('myprobe7','minimum', '1-3','current load')
            self.bs.add_hosts_probe_one_shot('myprobe8','minimum', '1-3','average load')
            self.bs.add_hosts_probe_one_shot('myprobe9','maximum', '1-3','energy consumed')
            self.bs.add_hosts_probe_one_shot('myprobe10','maximum', '1-3','power consumption')
            self.bs.add_hosts_probe_one_shot('myprobe11','maximum', '1-3','current load')
            self.bs.add_hosts_probe_one_shot('myprobe12','maximum', '1-3','average load')
            self.bs.add_hosts_probe_one_shot('myprobe13','average', '1-3','energy consumed')
            self.bs.add_hosts_probe_one_shot('myprobe14','average', '1-3','power consumption')
            self.bs.add_hosts_probe_one_shot('myprobe15','average', '1-3','current load')
            self.bs.add_hosts_probe_one_shot('myprobe16','average', '1-3','average load')
            self.bs.add_hosts_probe_one_shot('myprobe17','addition', '1-3','energy consumed')
            self.bs.add_hosts_probe_one_shot('myprobe18','addition', '1-3','power consumption')
            self.bs.add_hosts_probe_one_shot('myprobe19','addition', '1-3','current load')
            self.bs.add_hosts_probe_one_shot('myprobe20','addition', '1-3','average load')
            self.bs.add_hosts_probe_one_shot('myprobe41','median', '1-3','energy consumed')
            self.bs.add_hosts_probe_one_shot('myprobe42','median', '1-3','power consumption')
            self.bs.add_hosts_probe_one_shot('myprobe43','median', '1-3','current load')
            self.bs.add_hosts_probe_one_shot('myprobe44','median', '1-3','average load')
            self.bs.add_links_probe_one_shot('myprobe22','none', 'backbone' ,'energy consumed')
            self.bs.add_links_probe_one_shot('myprobe23','none', 'backbone' ,'average load')
            self.bs.add_links_probe_one_shot('myprobe24','none', 'backbone' ,'current load')
            self.bs.add_links_probe_one_shot('myprobe26','minimum', 'backbone' ,'energy consumed')
            self.bs.add_links_probe_one_shot('myprobe27','minimum', 'backbone' ,'average load')
            self.bs.add_links_probe_one_shot('myprobe28','minimum', 'backbone' ,'current load')
            self.bs.add_links_probe_one_shot('myprobe30','maximum', 'backbone' ,'energy consumed')
            self.bs.add_links_probe_one_shot('myprobe31','maximum', 'backbone' ,'average load')
            self.bs.add_links_probe_one_shot('myprobe32','maximum', 'backbone' ,'current load')
            self.bs.add_links_probe_one_shot('myprobe34','average', 'backbone' ,'energy consumed')
            self.bs.add_links_probe_one_shot('myprobe35','average', 'backbone' ,'average load')
            self.bs.add_links_probe_one_shot('myprobe36','average', 'backbone' ,'current load')
            self.bs.add_links_probe_one_shot('myprobe38','addition', 'backbone' ,'energy consumed')
            self.bs.add_links_probe_one_shot('myprobe39','addition', 'backbone' ,'average load')
            self.bs.add_links_probe_one_shot('myprobe45','addition', 'backbone' ,'current load')
            self.bs.add_links_probe_one_shot('myprobe46','median', 'backbone' ,'energy consumed')
            self.bs.add_links_probe_one_shot('myprobe47','median', 'backbone' ,'average load')
            self.bs.add_links_probe_one_shot('myprobe48','median', 'backbone' ,'current load')


    def onJobCompletion(self, job):
        # self.bs.add_hosts_probe('myprobe9','none', '1-3','energy consumed')
        # self.bs.add_hosts_probe('myprobe10','none', '1-3','power consumption')
        # self.bs.add_hosts_probe('myprobe11','none', '1-3','current load')
        # self.bs.add_hosts_probe('myprobe12','none', '1-3','average load')
        # self.bs.add_links_probe('myprobe13','none', 'backbone' ,'power consumption')
        # self.bs.add_links_probe('myprobe14','none', 'backbone' ,'energy consumed')
        # self.bs.add_links_probe('myprobe15','none', 'backbone' ,'average load')
        # self.bs.add_links_probe('myprobe16','none', 'backbone' ,'current load')
        self.availableResources |= job.allocation
        self.scheduleJobs()

