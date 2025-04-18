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
            self._handle_event(event)

    def _handle_event(self, event: Event) -> None:
        # we should not receive send-only events:
        # this could be done better with differentiated base classes
        match event:
            # receive-only events
            case JobSubmittedEvent():
                self.submit_job(event)
            case JobCompletedEvent():
                self.complete_job(event)
            case SimulationBeginsEvent():
                self.begin_simulation(event)
            case SimulationEndsEvent():
                self.end_simulation(event)
            case AllStaticJobsHaveBeenSubmittedEvent():
                pass

            # send-only events
            case EDCHelloEvent() | RejectJobEvent() | ExecuteJobEvent():
                err_msg = f"Unexpected send-only Event '{type(event).__name__}'"
                raise TypeError(err_msg)

            # catch-all for unknown events
            case _:
                err_msg = f"Unknown Event '{type(event).__name__}'"
                raise TypeError(err_msg)

    @abstractmethod
    def begin_simulation(self, event: SimulationBeginsEvent) -> None: ...

    @abstractmethod
    def end_simulation(self, event: SimulationEndsEvent) -> None: ...

    @abstractmethod
    def submit_job(self, event: JobSubmittedEvent) -> None: ...

    @abstractmethod
    def complete_job(self, event: JobCompletedEvent) -> None: ...

    def finalize(self):
        pass
