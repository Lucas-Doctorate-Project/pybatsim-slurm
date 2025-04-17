from random import sample

from procset import ProcSet

from pybatsim.batsim.batsim import ExternalDecisionComponent
from pybatsim.batsim.core import SimulationFeatures
from pybatsim.batsim.events import (
    AllStaticJobsHaveBeenSubmittedEvent,
    EDCHelloEvent,
    ExecuteJobEvent,
    JobCompletedEvent,
    JobSubmittedEvent,
    RejectJobEvent,
    SimulationBeginsEvent,
    SimulationEndsEvent,
)


class RandomSched(ExternalDecisionComponent):
    def __init__(self, batsim, options):
        self._batsim = batsim
        self._options = options
        self.scheduling_needed = False

        self._batsim.simulation_metadata.requested_features |= \
                SimulationFeatures.FORWARD_PROFILES_ON_JOB_SUBMISSION

        self._batsim.add_event(EDCHelloEvent(self._batsim.time,
                                             self._batsim.simulation_metadata,
                                             "RandomSched", "v0.1", ""))


    def handle_SimulationBegins(self, event):
        #TODO: update this if info from SimulationBegins are sent in BatsimHello event
        self.nb_compute_res = event.computation_host_number
        self.available_res = ProcSet((0, self.nb_compute_res-1))
        self.waiting_jobs = set()
        self.running_jobs = {}


    def handle_msg(self, message):
        for event in message:
            match event:
                case SimulationBeginsEvent():
                    self.handle_SimulationBegins(event)
                case SimulationEndsEvent():
                    pass
                case JobSubmittedEvent():
                    self.handle_JobSubmitted(event)
                case JobCompletedEvent():
                    self.handle_JobCompleted(event)
                case AllStaticJobsHaveBeenSubmittedEvent():
                    pass
                case _:
                    raise NotImplementedError(f"Handling of event type '{type(event).__name__}' not implemented")

        if self.scheduling_needed:
            self.do_schedule()
            self.scheduling_needed = False


    def handle_JobSubmitted(self, event):
        j = event.job
        if j.resource_request > self.nb_compute_res:
            self._batsim.add_event(RejectJobEvent(self._batsim.time, j.job_id))

        self.waiting_jobs.add(j)
        self.scheduling_needed = True


    def handle_JobCompleted(self, event):
        j = self.running_jobs.pop(event.job_id)
        self.available_res |= j.allocation
        self.scheduling_needed = True


    def do_schedule(self):
        scheduledJobs = []

        for j in self.waiting_jobs:
            if j.resource_request <= len(self.available_res):
                res = sample(list(self.available_res), j.resource_request)
                print(f"Selected {res} for job {j.job_id}")
                j.allocation = ProcSet(*res)

                self.available_res -= j.allocation
                scheduledJobs.append(j)

        for j in scheduledJobs:
            self.waiting_jobs.remove(j)
            self.running_jobs[j.job_id] = j
            self._batsim.add_event(ExecuteJobEvent(self._batsim.time, j))

        self.scheduling_needed = False
