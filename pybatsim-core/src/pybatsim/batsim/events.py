from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar, Final, override

from procset import ProcSet

from .core import SimulationMetadata
from .job import FinalState, Job, JobId
from .profile import Profile

"""
The following batprotocol v1.0.0 events have an experimental implementation.
They may change behavior in a breaking manner upon minor version update.

- ExecuteJobEvent
- JobsKilledEvent
- RegisterProfileEvent
- SimulationBeginsEvent


The following batprotocol v1.0.0 events are unsupported.
They may be implemented in a subsequent minor version.

- CreateProbeEvent
- StopProbeEvent
- TriggerProbeEvent
- ResetProbeEvent
- ProbeDataEmittedEvent
"""


def __experimental(*, reason: str | None = None):
    """Decorator to identify experimental features."""

    def decorator(obj):
        # Craft experimental note.
        entity_type = 'class' if isinstance(obj, type) else 'function'
        note = f'This {entity_type} is experimental and is subject to backward-incompatible changes upon minor releases.'  # noqa: E501 (reason: grepability)
        if reason:
            note += f'\nReason: {reason}'

        # Update docstring.
        if obj.__doc__:
            obj.__doc__ += f'\n\n{note}'
        else:
            obj.__doc__ = note

        return obj

    return decorator


# abstract base classes  -------------------------------------------------------


class Event:
    _batprotocol_events: Final[ClassVar[dict[str, type[Event]]]] = {}

    timestamp: float

    def __new__(cls, *_args, **_kwargs):
        # Ensure Event, RxEvent or TxEvent are not instantiated, see:
        # - https://stackoverflow.com/a/7990308
        # - https://docs.python.org/3/reference/datamodel.html#object.__new__
        if cls in (Event, RxEvent, TxEvent):
            err_msg = f'Cannot instantiate abstract class {cls.__name__}'
            raise TypeError(err_msg)

        # We pass only cls to object.__new__() as we also define __init__().
        # However, we need to keep args and kwargs in the signature as they are
        # forwarded to __init__().
        return object.__new__(cls)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._batprotocol_events[cls.__name__] = cls

    def __init__(self, timestamp: float):
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


# TODO(rb):
#   dispatch elements of _payload to attributes with semantic types:
#     - SimulationMetadata
#     - (to create/define) Simulation(Args|Params|Context)
@__experimental(reason='_payload is yet to be mapped to semantic types.')
class SimulationBeginsEvent(RxEvent):
    _payload: dict

    @override
    def __init__(self, timestamp: float, payload: dict):
        super().__init__(timestamp)
        self._payload = payload

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> SimulationBeginsEvent:
        return cls(
            timestamp=payload['timestamp'],
            payload=payload['event'],
        )

    @property
    def computation_host_number(self) -> int:
        return self._payload['computation_host_number']


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
    def __init__(self, timestamp: float, job: Job):
        super().__init__(timestamp)
        self.job = job

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> JobSubmittedEvent:
        job = Job(
            job_id=payload['event']['job_id'],
            resource_request=payload['event']['job']['resource_request'],
            walltime=payload['event']['job']['walltime'],
            profile_id=payload['event']['job']['profile_id'],
            extra_data=payload['event']['job'].get('extra_data'),
        )
        job.submission_time = payload['event']['submission_time']
        job.profile_dict = payload['event'].get('profile')

        return cls(
            timestamp=payload['timestamp'],
            job=job,
        )


class JobCompletedEvent(RxEvent):
    job: Job
    state: FinalState
    return_code: int

    @override
    def __init__(self, timestamp: float, job: Job, state: FinalState, return_code: int):
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
            state=FinalState(payload['event']['state']),
            return_code=payload['event']['return_code'],
        )


@__experimental(reason='progress is yet to be mapped to a semantic type.')
class JobsKilledEvent(RxEvent):
    # TODO(rb): consider using a list of tuples
    jobs: list[Job]
    progresses: dict[JobId, dict] = {}

    @override
    def __init__(
        self, timestamp: float, jobs: list[Job], progresses: dict[JobId, dict]
    ):
        super().__init__(timestamp)
        self.jobs = jobs
        self.progresses = progresses

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> JobsKilledEvent:
        progresses: dict[JobId, dict] = {}
        for progress_dict in payload['event']['progresses']:
            job_id = progress_dict['job_id']
            # TODO: correctly deserialise the wrapped progress in a KillProgress object
            progresses[job_id] = progress_dict['wrapper']

        return cls(
            timestamp=payload['timestamp'],
            jobs=payload['__pybatsim_dead_jobs'],  # injected by deserialisation
            progresses=progresses,
        )


class RequestedCallEvent(RxEvent):
    call_id: str
    is_last_call: bool

    @override
    def __init__(self, timestamp: float, call_id: str, is_last_call: bool):
        super().__init__(timestamp)
        self.call_id = call_id
        self.is_last_call = is_last_call

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> RequestedCallEvent:
        return cls(
            timestamp=payload['timestamp'],
            call_id=payload['event']['call_me_later_id'],
            is_last_call=payload['event']['last_periodic_call'],
        )


class ExternalEventOccurredEvent(RxEvent):
    external_event_id: str
    # TODO: consider using an enum, might be overkill as there exists a single
    # type as of now (GenericExternalEvent)
    external_event_type: str
    external_event: dict

    @override
    def __init__(
        self,
        timestamp: float,
        external_event_id: str,
        external_event_type: str,
        external_event: dict,
    ):
        super().__init__(timestamp)
        self.external_event_id = external_event_id
        self.external_event_type = external_event_type
        self.external_event = external_event

    @override
    @classmethod
    def from_protocol_dict(cls, payload: dict) -> ExternalEventOccurredEvent:
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
    def from_protocol_dict(
        cls, payload: dict
    ) -> AllStaticExternalEventsHaveBeenInjectedEvent:
        return cls(
            timestamp=payload['timestamp'],
        )


class HostsPStateChangedEvent(RxEvent):
    host_ids: ProcSet
    pstate: int

    @override
    def __init__(self, timestamp: float, host_ids: ProcSet, pstate: int):
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
    def __init__(self, timestamp: float, host_ids: ProcSet, state: int):
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


class EDCHelloEvent(TxEvent):
    simulation_metadata: SimulationMetadata
    # TODO: consider integrating edc_* in simulation_metadata
    edc_name: str
    edc_version: str
    edc_commit: str

    @override
    def __init__(
        self,
        timestamp: float,
        simulation_metadata: SimulationMetadata,
        edc_name: str,
        edc_version: str,
        edc_commit: str,
    ):
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
    def __init__(self, timestamp: float, job: Job):
        super().__init__(timestamp)
        self.job = job

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        protocol_dict['event'] |= {
            'job_id': self.job.job_id,
        }
        return protocol_dict


@__experimental(reason='Placement policy will be coerced in a semantic type.')
class ExecuteJobEvent(TxEvent):
    job: Job
    # TODO: merge executor_placement, profile_allocation_override,
    # storage_placement in PlacementPolicy object
    executor_placement: Job.ExecutorPlacement
    profile_allocation_override: Any | None = None
    storage_placement: Any | None = None

    @override
    def __init__(
        self,
        timestamp: float,
        job: Job,
        executor_placement: Job.ExecutorPlacement | None = None,
        profile_allocation_override: Any | None = None,
        storage_placement: Any | None = None,
    ):
        super().__init__(timestamp)
        self.job = job
        self.executor_placement = (
            Job.ExecutorPlacement()
            if executor_placement is None
            else executor_placement
        )
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
    jobs: list[Job]

    @override
    def __init__(self, timestamp: float, jobs: list[Job]):
        super().__init__(timestamp)
        self.jobs = jobs

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        protocol_dict['event'] |= {
            'job_ids': [job.job_id for job in self.jobs],
        }
        return protocol_dict


class CallMeLaterEvent(TxEvent):
    # TODO: nesting class is not Pythonic
    class TemporalTriggerType(Enum):
        OneShot = 0
        Periodic = 1

    call_id: str
    when_type: TemporalTriggerType
    when: dict  # TODO: consider using an object

    @override
    def __init__(
        self,
        timestamp: float,
        call_id: str,
        when_type: TemporalTriggerType,
        when_dict: dict,
    ):
        super().__init__(timestamp)
        self.call_id = call_id
        self.when_type = when_type
        self.when = when_dict

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        protocol_dict['event'] |= {
            'call_me_later_id': self.call_id,
            'when_type': self.when_type.name,
            'when': self.when,
        }
        return protocol_dict


class StopCallMeLaterEvent(TxEvent):
    call_id: str

    @override
    def __init__(self, timestamp: float, call_id: str):
        super().__init__(timestamp)
        self.call_id = call_id

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        protocol_dict['event'] |= {
            'call_me_later_id': self.call_id,
        }
        return protocol_dict


class ForceSimulationStopEvent(TxEvent):
    # Empty payload: use base behavior.
    pass


class FinishRegistrationEvent(TxEvent):
    # Empty payload: use base behavior.
    pass


class RegisterJobEvent(TxEvent):
    job: Job

    @override
    def __init__(self, timestamp: float, job: Job):
        super().__init__(timestamp)
        self.job = job
        # XXX: job.submission_time will never be set if ack of dynamic jobs is
        # disabled: consider injecting timestamp as job.submission_time

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()

        job_dict = {
            'resource_request': self.job.resource_request,
            'walltime': self.job.walltime,
            'profile_id': self.job.profile_id,
        }
        if self.job.extra_data is not None:
            job_dict['extra_data'] = self.job.extra_data

        protocol_dict['event'] |= {
            'job_id': self.job.job_id,
            'job': job_dict,
        }

        return protocol_dict


@__experimental(reason='Profile will be mapped to a semantic type')
class RegisterProfileEvent(TxEvent):
    profile: Profile

    @override
    def __init__(self, timestamp: float, profile: Profile):
        super().__init__(timestamp)
        self.profile = profile

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()

        profile_dict = {
            'id': self.profile.profile_id,
            'profile_type': self.profile.profile_type.name,
            'profile': self.profile.profile_dict,
        }
        if self.profile.extra_data is not None:
            profile_dict['extra_data'] = self.profile.extra_data

        protocol_dict['event'] |= {'profile': profile_dict}

        return protocol_dict


class ChangeHostsPStateEvent(TxEvent):
    host_ids: ProcSet
    pstate: int

    @override
    def __init__(self, timestamp: float, host_ids: ProcSet, pstate: int):
        super().__init__(timestamp)
        self.host_ids = host_ids
        self.pstate = pstate

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        protocol_dict['event'] |= {
            'host_ids': str(self.host_ids),
            'pstate': self.pstate,
        }
        return protocol_dict


class TurnOnOffHostsEvent(TxEvent):
    host_ids: ProcSet
    state: int

    @override
    def __init__(self, timestamp: float, host_ids: ProcSet, state: int):
        super().__init__(timestamp)
        self.host_ids = host_ids
        self.state = state

    @override
    def to_protocol_dict(self) -> dict:
        protocol_dict = super().to_protocol_dict()
        protocol_dict['event'] |= {
            'host_ids': str(self.host_ids),
            'state': self.state,
        }
        return protocol_dict
