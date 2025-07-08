from abc import abstractmethod
from typing import Protocol

from .batsim import Batsim
from .events import (
    AllStaticJobsHaveBeenSubmittedEvent,
    AllStaticExternalEventsHaveBeenInjectedEvent,
    EDCHelloEvent,
    Event,
    TxEvent,
    ExecuteJobEvent,
    JobCompletedEvent,
    JobSubmittedEvent,
    RejectJobEvent,
    JobsKilledEvent,
    RequestedCallEvent,
    ExternalEventOccurredEvent,
    HostsPStateChangedEvent,
    HostsTurnedOnOffEvent,
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
        # We should not receive send-only events
        assert not isinstance(event, TxEvent), f"Unexpected send-only Event '{type(event).__name__}'"

        match event:
            # receive-only events
            case JobSubmittedEvent():
                self.handle_submitted_job(event)
            case JobCompletedEvent():
                self.handle_completed_job(event)
            case JobsKilledEvent():
                self.handle_jobs_killed(event)
            case RequestedCallEvent():
                self.handle_requested_call(event)
            case ExternalEventOccurredEvent():
                self.handle_external_event_occurred(event)
            case HostsPStateChangedEvent():
                self.handle_hosts_pstate_changed(event)
            case HostsTurnedOnOffEvent():
                self.handle_hosts_turned_onoff(event)
            case SimulationBeginsEvent():
                self.handle_simulation_begins(event)
            case SimulationEndsEvent():
                self.handle_simulation_ends(event)
            case AllStaticJobsHaveBeenSubmittedEvent():
                self.handle_no_more_static_jobs(event)
            case AllStaticExternalEventsHaveBeenInjectedEvent():
                self.handle_no_more_external_events(event)

            # catch-all for unknown events
            case _:
                err_msg = f"Unknown Event '{type(event).__name__}'"
                raise TypeError(err_msg)

    @abstractmethod
    def handle_simulation_begins(self, event: SimulationBeginsEvent) -> None: ...

    @abstractmethod
    def handle_simulation_ends(self, event: SimulationEndsEvent) -> None: ...

    @abstractmethod
    def handle_submitted_job(self, event: JobSubmittedEvent) -> None: ...

    @abstractmethod
    def handle_completed_job(self, event: JobCompletedEvent) -> None: ...

    @abstractmethod
    def handle_jobs_killed(self, event: JobsKilledEvent) -> None: ...

    @abstractmethod
    def handle_external_event_occurred(self, event: ExternalEventOccurredEvent) -> None: ...

    @abstractmethod
    def handle_hosts_pstate_changed(self, event: HostsPStateChangedEvent) -> None: ...

    @abstractmethod
    def handle_hosts_turned_onoff(self, event: HostsTurnedOnOffEvent) -> None: ...

    @abstractmethod
    def handle_requested_call(self, event: RequestedCallEvent) -> None: ...

    def handle_no_more_static_jobs(self, event: AllStaticJobsHaveBeenSubmittedEvent):
        pass

    def handle_no_more_external_events(self, event: AllStaticExternalEventsHaveBeenInjectedEvent):
        pass

    def finalize(self):
        pass
