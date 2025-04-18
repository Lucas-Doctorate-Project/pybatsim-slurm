from random import Random

from procset import ProcSet

from pybatsim.batsim.batsim import Batsim
from pybatsim.batsim.core import SimulationFeatures
from pybatsim.batsim.edc import Scheduler
from pybatsim.batsim.events import (
    EDCHelloEvent,
    ExecuteJobEvent,
    JobCompletedEvent,
    JobSubmittedEvent,
    RejectJobEvent,
    SimulationBeginsEvent,
    SimulationEndsEvent,
)
from pybatsim.batsim.job import Job


class RandomScheduler(Scheduler):
    waiting_jobs: set[Job] = set()
    running_jobs: dict[str, Job] = {}
    idle_resources: ProcSet | None = None
    cluster_size: int | None = None
    _generator: Random

    def __init__(self, batsim: Batsim, options: str | None = None):
        super().__init__(batsim, options)
        self._generator = Random(42)  # TODO: provide mechanism to select seed

        self._batsim.simulation_metadata.requested_features |= (
            SimulationFeatures.FORWARD_PROFILES_ON_JOB_SUBMISSION
        )
        edc_hello_event = EDCHelloEvent(
            timestamp=self._batsim.time,
            simulation_metadata=self._batsim.simulation_metadata,
            edc_name=type(self).__name__,
            edc_version='0.0.0',
            edc_commit='',
        )
        self._batsim.add_event(edc_hello_event)

    def begin_simulation(self, event: SimulationBeginsEvent) -> None:
        self.cluster_size = event.computation_host_number
        self.idle_resources = ProcSet((0, self.cluster_size - 1))

    def end_simulation(self, event: SimulationEndsEvent) -> None:
        pass

    def submit_job(self, event: JobSubmittedEvent) -> None:
        job = event.job

        if job.resource_request > self.cluster_size:
            # trivial reject if job request more resources than cluster_size
            reject_event = RejectJobEvent(
                timestamp=self._batsim.time,
                job_id=job.job_id,
            )
            self._batsim.add_event(reject_event)
        else:
            self.waiting_jobs.add(job)

    def complete_job(self, event: JobCompletedEvent) -> None:
        job = self.running_jobs.pop(event.job_id)
        self.idle_resources |= job.allocation

    def handle_msg(self, msg) -> None:
        super().handle_msg(msg)
        self.schedule_jobs()

    def schedule_jobs(self):
        scheduled_jobs = []

        for job in self.waiting_jobs:
            # randomly assign resources if enough resources are idle
            if job.resource_request <= len(self.idle_resources):
                allocation = self._generator.sample(
                    population=list(self.idle_resources),
                    k=job.resource_request,
                )
                job.allocation = ProcSet(*allocation)
                self.idle_resources -= job.allocation
                scheduled_jobs.append(job)

        # remove scheduled_jobs from waiting_jobs
        self.waiting_jobs.difference_update(scheduled_jobs)

        # send the list of scheduled jobs to Batsim
        for job in scheduled_jobs:
            self.running_jobs[job.job_id] = job
            execute_event = ExecuteJobEvent(
                timestamp=self._batsim.time,
                job=job,
            )
            self._batsim.add_event(execute_event)
