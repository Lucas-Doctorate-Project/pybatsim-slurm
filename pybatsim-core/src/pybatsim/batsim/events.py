from __future__ import annotations

from typing import Any, ClassVar, Final, override

from .core import SimulationMetadata
from .job import Job

'''
List of batprotocol events:

      OK JobSubmittedEvent
      OK JobCompletedEvent
      OK RejectJobEvent
      OK ExecuteJobEvent
    TODO KillJobsEvent
    TODO JobsKilledEvent

    TODO RegisterProfileEvent
    TODO RegisterJobEvent

    TODO CreateProbeEvent
    TODO StopProbeEvent
    TODO TriggerProbeEvent
    TODO ResetProbeEvent
    TODO ProbeDataEmittedEvent
    TODO CallMeLaterEvent
    TODO RequestedCallEvent
    TODO StopCallMeLaterEvent

    TODO BatsimHelloEvent
      OK EDCHelloEvent
      OK SimulationBeginsEvent
      OK SimulationEndsEvent

      ?? AllStaticJobsHaveBeenSubmittedEvent
    TODO AllStaticExternalEventsHaveBeenInjectedEvent
    TODO FinishRegistrationEvent
    TODO ForceSimulationStopEvent

    TODO ChangeHostPStateEvent
    TODO HostPStateChangedEvent
    TODO ExternalEventOccurredEvent
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


class SimulationBeginsEvent(RxEvent):
    computation_host_number: int

    @override
    def __init__(self, timestamp, computation_host_number):
        super().__init__(timestamp)
        self.computation_host_number = computation_host_number

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> SimulationBeginsEvent:
        return cls(
            timestamp=payload['timestamp'],
            computation_host_number=payload['event']['computation_host_number'],
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


class AllStaticJobsHaveBeenSubmittedEvent(RxEvent):
    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> AllStaticJobsHaveBeenSubmittedEvent:
        return cls(
            timestamp=payload['timestamp'],
        )


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
