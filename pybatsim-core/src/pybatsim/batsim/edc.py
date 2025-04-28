from abc import abstractmethod
from typing import Protocol

from .batsim import Batsim
from .events import (
    AllStaticJobsHaveBeenSubmittedEvent,
    EDCHelloEvent,
    Event,
    ExecuteJobEvent,
    JobCompletedEvent,
    JobSubmittedEvent,
    RejectJobEvent,
    SimulationBeginsEvent,
    SimulationEndsEvent,
)


class ExternalDecisionComponent(Protocol):
    def __init__(self, batsim: Batsim, options=None): ...

    def handle_msg(self, msg) -> None: ...

    def finalize(self) -> None: ...


class Scheduler(ExternalDecisionComponent):
    _batsim: Batsim
    _options: str | None

    def __init__(self, batsim: Batsim, options: str | None = None):
        self._batsim = batsim
        self._options = options

    def handle_msg(self, msg) -> None:
        for event in msg:
            self._dispatch(event)

    def _dispatch(self, event: Event) -> None:
        # we should not receive send-only events:
        # this could be done better with differentiated base classes
        match event:
            # receive-only events
            case JobSubmittedEvent():
                self.handle_submitted_job(event)
            case JobCompletedEvent():
                self.handle_completed_job(event)
            case SimulationBeginsEvent():
                self.handle_simulation_begin(event)
            case SimulationEndsEvent():
                self.handle_simulation_end(event)
            case AllStaticJobsHaveBeenSubmittedEvent():
                self.handle_no_more_static_jobs(event)

            # send-only events
            case EDCHelloEvent() | RejectJobEvent() | ExecuteJobEvent():
                err_msg = f"Unexpected send-only Event '{type(event).__name__}'"
                raise TypeError(err_msg)

            # catch-all for unknown events
            case _:
                err_msg = f"Unknown Event '{type(event).__name__}'"
                raise TypeError(err_msg)

    @abstractmethod
    def handle_simulation_begin(self, event: SimulationBeginsEvent) -> None: ...

    @abstractmethod
    def handle_simulation_end(self, event: SimulationEndsEvent) -> None: ...

    @abstractmethod
    def handle_submitted_job(self, event: JobSubmittedEvent) -> None: ...

    @abstractmethod
    def handle_completed_job(self, event: JobCompletedEvent) -> None: ...

    def handle_no_more_static_jobs(self, event: AllStaticJobsHaveBeenSubmittedEvent):
        pass

    def finalize(self):
        pass
