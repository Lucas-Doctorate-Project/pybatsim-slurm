from __future__ import annotations

from typing import Any, ClassVar, Final, override
from enum import Enum
from procset import ProcSet

from .core import SimulationMetadata
from .job import Job

'''
List of batprotocol events:

      OK JobSubmittedEvent
      OK JobCompletedEvent
      OK RejectJobEvent
      OK ExecuteJobEvent
      Ok KillJobsEvent
      OK JobsKilledEvent

    TODO RegisterProfileEvent
    TODO RegisterJobEvent
    TODO FinishRegistrationEvent

    TODO CreateProbeEvent
    TODO StopProbeEvent
    TODO TriggerProbeEvent
    TODO ResetProbeEvent
    TODO ProbeDataEmittedEvent
      OK CallMeLaterEvent
      OK RequestedCallEvent
      OK StopCallMeLaterEvent

      OK EDCHelloEvent
      OK SimulationBeginsEvent
      OK SimulationEndsEvent

      OK AllStaticJobsHaveBeenSubmittedEvent
      OK AllStaticExternalEventsHaveBeenInjectedEvent
      OK ForceSimulationStopEvent
      OK SimulationErrorEvent
      OK ExternalEventOccurredEvent

      OK ChangeHostPStateEvent
      OK HostPStateChangedEvent
      OK TurnOnOffHostsEvent
      OK HostsTurnedOnOffEvent
'''


# abstract base classes  -------------------------------------------------------


class Event:
    _batprotocol_events: Final[ClassVar[dict[str, type[Event]]]] = {}

    timestamp: float

    def __new__(cls, *_args, **_kwargs):
        # ensure Event, RxEvent or TxEvent are not instantiated, see:
        # - https://stackoverflow.com/a/7990308
        # - https://docs.python.org/3/reference/datamodel.html#object.__new__
        if cls in (Event, RxEvent, TxEvent):
            err_msg = f'Cannot instantiate abstract class {cls.__name__}'
            raise TypeError(err_msg)

        # We pass only cls to object.__new__() as we also define __init__().
        # However, we need to keep args and kwargs in the signature as they
        # are forwarded to __init__().
        return object.__new__(cls)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._batprotocol_events[cls.__name__] = cls

    def __init__(self, timestamp):
        self.timestamp = timestamp


class RxEvent(Event):
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> RxEvent:
        concrete_cls = cls._batprotocol_events[payload['event_type']]
        assert issubclass(concrete_cls, RxEvent), 'expected a receive event'
        return concrete_cls.from_protocol_dict(payload)


class TxEvent(Event):
    def to_protocol_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'event_type': type(self).__name__,
            'event': {},
        }


# concrete classes  ------------------------------------------------------------

######################
######################
## RxEvent classes  ------------------------------------------------------------
######################
######################

class SimulationBeginsEvent(RxEvent):
    whole_dict: dict
    computation_host_number: int
    # TODO: Handle me correctly. Put all information in separate attributes?

    @override
    def __init__(self, timestamp, whole_dict):
        super().__init__(timestamp)
        self.whole_dict = whole_dict
        self.computation_host_number = whole_dict['computation_host_number']

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> SimulationBeginsEvent:
        return cls(
            timestamp=payload['timestamp'],
            whole_dict=payload['event'],
        )


class SimulationEndsEvent(RxEvent):
    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> SimulationEndsEvent:
        return cls(
            timestamp=payload['timestamp'],
        )


class JobSubmittedEvent(RxEvent):
    job: Job

    @override
    def __init__(self, timestamp, job):
        super().__init__(timestamp)
        self.job = job

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> JobSubmittedEvent:
        return cls(
            timestamp=payload['timestamp'],
            job=Job.from_protocol_dict(payload['event']),
        )


class JobCompletedEvent(RxEvent):
    job: Job
    state: Any  # XXX: assign real type
    return_code: int

    @override
    def __init__(self, timestamp, job, state, return_code):
        super().__init__(timestamp)
        self.job = job
        self.state = state
        self.return_code = return_code

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> JobCompletedEvent:
        assert payload['__pybatsim_job'].job_id == payload['event']['job_id']
        return cls(
            timestamp=payload['timestamp'],
            job=payload['__pybatsim_job'],  # injected by deserialisation
            state=payload['event']['state'],
            return_code=payload['event']['return_code'],
        )

class JobsKilledEvent(RxEvent):
    jobs: [Job]

    @override
    def __init__(self, timestamp, jobs, progresses):
        super().__init__(timestamp)
        self.jobs = jobs
        self.progresses = progresses

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> JobsKilledEvent:
        progresses: dict[str, dict] = {}
        for progress_dict in payload['event']['progresses']:
            job_id = progress_dict['job_id']
            # TODO: correctly deserialise the wrapped progress in a KillProgress object
            progresses[job_id] = progress_dict['wrapper']

        return cls(
            timestamp=payload['timestamp'],
            jobs=payload['__pybatsim_jobs'], # injected by deserialisation
            progresses=progresses,
        )

class RequestedCallEvent(RxEvent):
    call_me_later_id: str
    last_periodic_call: bool

    @override
    def __init__(self, timestamp, call_id, last_call):
        super().__init__(timestamp)
        self.call_me_later_id = call_id
        self.last_periodic_call = last_call

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> RequestedCallEvent:
        return cls(
            timestamp=payload['timestamp'],
            call_id=payload['event']['call_me_later_id'],
            last_call=payload['event']['last_periodic_call'],
        )


class ExternalEventOccurredEvent(RxEvent):
    external_event_id: str
    # TODO: make the event type an Enum? But for the moment only one type "GenericExternalEvent"
    external_event_type: str
    external_event: dict

    @override
    def __init__(self, timestamp, external_event_id, external_event_type, external_event):
        super().__init__(timestamp)
        self.external_event_id = external_event_id
        self.external_event_type = external_event_type
        self.external_event = external_event

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> RequestedCallEvent:
        return cls(
            timestamp=payload['timestamp'],
            external_event_id=payload['event']['id'],
            external_event_type=payload['event']['external_event_type'],
            external_event=payload['event']['external_event'],
        )


class AllStaticJobsHaveBeenSubmittedEvent(RxEvent):
    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> AllStaticJobsHaveBeenSubmittedEvent:
        return cls(
            timestamp=payload['timestamp'],
        )

class AllStaticExternalEventsHaveBeenInjectedEvent(RxEvent):
    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> AllStaticExternalEventsHaveBeenInjectedEvent:
        return cls(
            timestamp=payload['timestamp'],
        )

class SimulationErrorEvent(RxEvent):
    error: str

    @override
    def __init__(self, timestamp, error):
        super().__init__(timestamp)
        self.error = error

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> SimulationErrorEvent:
        return cls(
            timestamp=payload['timestamp'],
            error=payload['event']['error'],
        )


class HostsPStateChangedEvent(RxEvent):
    host_ids: ProcSet
    pstate: int

    @override
    def __init__(self, timestamp, host_ids, pstate):
        super().__init__(timestamp)
        self.host_ids = host_ids
        self.pstate = pstate

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> HostsPStateChangedEvent:
        return cls(
            timestamp=payload['timestamp'],
            host_ids=ProcSet.from_str(payload['event']['host_ids']),
            pstate=payload['event']['pstate'],
        )


class HostsTurnedOnOffEvent(RxEvent):
    host_ids: ProcSet
    state: int

    @override
    def __init__(self, timestamp, host_ids, state):
        super().__init__(timestamp)
        self.host_ids = host_ids
        self.state = state

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> HostsTurnedOnOffEvent:
        return cls(
            timestamp=payload['timestamp'],
            host_ids=ProcSet.from_str(payload['event']['host_ids']),
            state=payload['event']['state'],
        )


######################
######################
## TxEvent classes  ------------------------------------------------------------
######################
######################


class EDCHelloEvent(TxEvent):
    simulation_metadata: SimulationMetadata
    # TODO: consider integrating edc_* in simulation_metadata
    edc_name: str
    edc_version: str
    edc_commit: str

    @override
    def __init__(self, timestamp, simulation_metadata, edc_name, edc_version, edc_commit):
        super().__init__(timestamp)
        self.simulation_metadata = simulation_metadata
        self.edc_name = edc_name
        self.edc_version = edc_version
        self.edc_commit = edc_commit

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        payload = protocol_dict['event']

        payload |= self.simulation_metadata.to_protocol_dict()
        payload |= {
            'decision_component_name': self.edc_name,
            'decision_component_version': self.edc_version,
            'decision_component_commit': self.edc_commit,
        }

        return protocol_dict


class RejectJobEvent(TxEvent):
    job: Job

    @override
    def __init__(self, timestamp, job: Job):
        super().__init__(timestamp)
        self.job = job

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        payload = protocol_dict['event']

        payload |= {
            'job_id': self.job.job_id,
        }

        return protocol_dict


class ExecuteJobEvent(TxEvent):
    job: Job
    # TODO: merge executor_placement, profile_allocation_override, storage_placement in PlacementPolicy object
    executor_placement: Job.ExecutorPlacement
    profile_allocation_override: Any | None = None
    storage_placement: Any | None = None

    @override
    def __init__(self, timestamp, job, executor_placement=None, profile_allocation_override=None, storage_placement=None):
        super().__init__(timestamp)
        self.job = job
        self.executor_placement = Job.ExecutorPlacement() if executor_placement is None else executor_placement
        self.profile_allocation_override = profile_allocation_override
        self.storage_placement = storage_placement

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        payload = protocol_dict['event']

        allocation = self.executor_placement.to_json_dict()
        allocation['host_allocation'] = str(self.job.allocation)

        payload |= {
            'job_id': self.job.job_id,
            'allocation': allocation,
        }

        # TODO: enhance handling of optional profile_allocation_override
        if self.profile_allocation_override is not None:
            payload['profile_allocation_override'] = self.profile_allocation_override

        # TODO: enhance handling of optional storage_placement
        if self.storage_placement is not None:
            payload['storage_placement'] = self.storage_placement

        return protocol_dict

class KillJobsEvent(TxEvent):
    jobs: [Job]

    @override
    def __init__(self, timestamp, jobs):
        super().__init__(timestamp)
        self.jobs = jobs

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        payload = protocol_dict['event']

        payload |= {
            'job_ids': [job.job_id for job in self.jobs]
        }

        return protocol_dict


class CallMeLaterEvent(TxEvent):

    class TemporalTriggerType(Enum):
        OneShot = 0
        Periodic = 1

    call_me_later_id: str
    when_type: TemporalTriggerType
    when: dict

    @override
    def __init__(self, timestamp, call_id, when_type, when_dict):
        super().__init__(timestamp)
        self.call_me_later_id = call_id
        self.when_type = when_type
        self.when = when_dict

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        payload = protocol_dict['event']

        payload |= {
            'call_me_later_id': self.call_me_later_id,
            'when_type': self.when_type.name,
            'when': self.when, # TODO: make it an object? (but REALLY VERBOSE)
        }

        return protocol_dict

class StopCallMeLaterEvent(TxEvent):
    call_me_later_id: str

    @override
    def __init__(self, timestamp, call_id):
        super().__init__(timestamp)
        self.call_me_later_id = call_id

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        payload = protocol_dict['event']

        payload |= {
            'call_me_later_id': self.call_me_later_id,
        }

        return protocol_dict

class ForceSimulationStopEvent(TxEvent):
    pass
    # Nothing specific for this event, its payload is empty


class ChangeHostsPStateEvent(TxEvent):
    host_ids: ProcSet
    pstate: int

    @override
    def __init__(self, timestamp, host_ids, pstate):
        super().__init__(timestamp)
        self.host_ids = host_ids
        self.pstate = pstate

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        payload = protocol_dict['event']

        payload |= {
            'host_ids': str(self.host_ids),
            'pstate': self.pstate
        }

        return protocol_dict

class TurnOnOffHostsEvent(TxEvent):
    host_ids: ProcSet
    state: int

    @override
    def __init__(self, timestamp, host_ids, state):
        super().__init__(timestamp)
        self.host_ids = host_ids
        self.state = state

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        payload = protocol_dict['event']

        payload |= {
            'host_ids': str(self.host_ids),
            'state': self.state
        }

        return protocol_dict
