from enum import Enum

from .job import Job

''' List of batprotocol event types '''
class EventType(Enum):
    JobSubmittedEvent = 1
    JobCompletedEvent = 2
    RejectJobEvent = 3
    ExecuteJobEvent = 4
    KillJobsEvent = 5
    JobsKilledEvent = 6

    RegisterProfileEvent = 7
    RegisterJobEvent = 8

    CreateProbeEvent = 9
    StopProbeEvent = 10
    TriggerProbeEvent = 11
    ResetProbeEvent = 12
    ProbeDataEmittedEvent = 13
    CallMeLaterEvent = 14
    RequestedCallEvent = 15
    StopCallMeLaterEvent = 16

    BatsimHelloEvent = 17
    EDCHelloEvent = 18
    SimulationBeginsEvent = 19
    SimulationEndsEvent = 20

    AllStaticJobsHaveBeenSubmittedEvent = 21
    AllStaticExternalEventsHaveBeenInjectedEvent = 22
    FinishRegistrationEvent = 23
    ForceSimulationStopEvent = 24

    ChangeHostPStateEvent = 25
    HostPStateChangedEvent = 26
    ExternalEventOccurredEvent = 27
# End of enum class EventType


# Abstract class
class Event:
    def __init__(self, timestamp, event_type, event_dict):
        self.timestamp = timestamp
        self.type = event_type
        self.data = event_dict

    def to_json_dict(self):
        self._write_data_dict()
        return {
            "timestamp": self.timestamp,
            "event_type": self.type.name,
            "event": self.data
        }

    # Method that must be implemented by a child class
    # for an event created by the EDC
    def _write_data_dict(self):
        pass

    @classmethod
    def from_json_dict(cls, json_dict):
        match EventType[json_dict["event_type"]]:
            #case EventType.BatsimHelloEvent:
            #    return cls(json_dict["timestamp"], EventType[json_dict["event_type"]], json_dict["event"])
            #case EventType.SimulationBeginsEvent:
            #    return SimulationBeginsEvent.from_json_dict(json_dict)
            #case EventType.SimulationEndsEvent:
            #    #return SimulationEndsEvent(json_dict)
            #    return cls(json_dict["timestamp"], EventType[json_dict["event_type"]], {})
            #case EventType.AllStaticJobsHaveBeenSubmittedEvent:
            #    return cls(json_dict["timestamp"], EventType[json_dict["event_type"]], {})
            case EventType.JobSubmittedEvent:
                return JobSubmittedEvent.from_json_dict(json_dict)
            case EventType.JobCompletedEvent:
                return JobCompletedEvent.from_json_dict(json_dict)
            case _:
                return cls(json_dict["timestamp"], EventType[json_dict["event_type"]], json_dict["event"])
                #raise ValueError(f"Unknown event type: '{json_dict['event_type']}'")


# Batsim -> EDC
#class SimulationBeginsEvent(Event):


# Batsim -> EDC
class JobSubmittedEvent(Event):
    def __init__(self, timestamp, job):
        self.type = EventType.JobSubmittedEvent
        self.timestamp = timestamp
        self.job = job

    @classmethod
    def from_json_dict(cls, json_dict):
        return cls(json_dict["timestamp"], Job.from_json_dict(json_dict["event"]))


# Batsim -> EDC
class JobCompletedEvent(Event):
    def __init__(self, timestamp, job_id, state, return_code):
        self.type = EventType.JobCompletedEvent
        self.timestamp = timestamp
        self.job_id = job_id
        self.state = state
        self.return_code = return_code

    @classmethod
    def from_json_dict(cls, json_dict):
        return cls(json_dict["timestamp"],
                   json_dict["event"]["job_id"],
                   json_dict["event"]["state"],
                   json_dict["event"]["return_code"])


# EDC -> Batsim
class EDCHelloEvent(Event):
    # TODO: put EDC name/version/commit in simulation_metadata?
    def __init__(self, timestamp, simulation_metadata,
                 EDC_name, EDC_version, EDC_commit):
        self.type = EventType.EDCHelloEvent
        self.timestamp = timestamp
        self.EDC_name = EDC_name
        self.EDC_version = EDC_version
        self.EDC_commit = EDC_commit
        self.simulation_metadata = simulation_metadata
        self.data = {}


    def _write_data_dict(self):
        self.data = self.simulation_metadata.to_protocol_dict()
        self.data |= {
            "decision_component_name": self.EDC_name,
            "decision_component_version": self.EDC_version,
            "decision_component_commit": self.EDC_commit,
        }


# EDC -> Batsim
class RejectJobEvent(Event):
    def __init__(self, timestamp, job_id):
        self.type = EventType.RejectJobEvent
        self.timestamp = timestamp
        self.job_id = job_id

    def _write_data_dict(self):
        self.data = {"data": {"job_id": self.job_id}}


# EDC -> Batsim
class ExecuteJobEvent(Event):
    def __init__(self, timestamp, job,
                 executor_placement = None,
                 profile_alloc_override = None,
                 storage_placement = None):
        self.type = EventType.ExecuteJobEvent
        self.timestamp = timestamp
        self.job = job

        self.exec_placement = executor_placement if executor_placement is not None else Job.ExecutorPlacement()
        self.profile_alloc_override = profile_alloc_override
        self.storage_placement = storage_placement


    def _write_data_dict(self):
        alloc_dict = self.exec_placement.to_json_dict()
        alloc_dict["host_allocation"] = str(self.job.allocation)
        self.data = {
            "job_id": self.job.job_id,
            "allocation": alloc_dict,
        }

        #TODO: need to correctly handle optional profile_allocation_override list (by providing QoL object/methods)
        if self.profile_alloc_override is not None:
            self.data["profile_allocation_override"] = self.profile_alloc_override

        #TODO: need to correctly handle optional storage_placement list (by providing QoL object/methods)
        if self.storage_placement is not None:
            self.data["storage_placement"] = self.storage_placement
