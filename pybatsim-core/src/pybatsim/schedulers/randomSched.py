from random import sample

from procset import ProcSet

from pybatsim.batsim.batsim import ExternalDecisionComponent, EventType, Job


class RandomSched(ExternalDecisionComponent):
    def __init__(self, batsim, options):
        self._batsim = batsim
        self._options = options

        self._batsim._simulation_context.forward_profiles_on_job_submission = True

        self._batsim.add_event(self._batsim.create_EDCHelloEvent("RandomSched", "v0.1"))
        self._batsim.register_EDC(self)

    def handle_SimulationBegins(self, event):
        #TODO: update this if info from SimulationBegins are sent in BatsimHello event
        self.nb_compute_res = event.data["computation_host_number"]
        self.available_res = ProcSet(0, self.nb_compute_res)
        self.waiting_jobs = set()
        self.running_jobs = {}


    def handle_message(self, message):
        for event in message:
            match event.type:
                case EventType.SimulationBeginsEvent:
                    self.handle_SimulationBegins(event)
                case EventType.SimulationEndsEvent:
                    pass
                case EventType.JobSubmittedEvent:
                    self.handle_JobSubmitted(event)
                case EventType.JobCompletedEvent:
                    self.handle_JobCompleted(event)
                case EventType.AllStaticJobsHaveBeenSubmittedEvent:
                    print("All static jobs have been submitted")
                case _:
                    raise NotImplementedError(f"Handling of event type '{event.type.name}' not implemented")

        if self.scheduling_needed:
            self.do_schedule()
            self.scheduling_needed = False


    def handle_JobSubmitted(self, event):
        j = Job.from_json_dict(event.data)
        if j.resource_request > self.nb_compute_res:
            self._batsim.add_event(self._batsim.create_RejectJobEvent(j.job_id))

        self.waiting_jobs.add(j)
        self.scheduling_needed = True


    def handle_JobCompleted(self, event):
        j = self.running_jobs.pop(event.data["job_id"])
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
            self._batsim.add_event(self._batsim.create_ExecuteJobEvent(j))

        self.scheduling_needed = False
