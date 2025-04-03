import json
from collections import deque
from dataclasses import dataclass
import sys
import zmq
import logging

from enum import Enum
from procset import ProcSet

from struct import unpack # TODO remove this

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

class Event:
    def __init__(self, timestamp, event_type, event_dict):
        self.timestamp = timestamp
        self.type = event_type
        self.data = event_dict

    def to_json_dict(self):
        return {
            "timestamp": self.timestamp,
            "event_type": self.type.name,
            "event": self.data
        }

    @staticmethod
    def from_json_dict(json_dict):
        return Event(json_dict["timestamp"],
                     EventType[json_dict["event_type"]],
                     json_dict["event"])


# TODO: move this outside of batsim.py
class ExternalDecisionComponent:
    def __init__(self, batsim, options = None):
        self._basim = batsim
        self._options = options

        self._batsim.add_EDCHello("UnknownEDC", "v0.0", "")
        self._batsim.register_EDC(self)

    def handle_message(self, message):
        raise NotImplementedError()

    def handle_SimulationBegins(self, event):
        pass

    def finish(self):
        pass



class Job:
    def __init__(self, job_id, submission_time, resource_request,
                 walltime, profile_id,
                 profile_dict = None, extra_data = None):
        self.job_id = job_id
        self.submission_time = submission_time
        self.resource_request = resource_request
        self.walltime = walltime
        self.profile_id = profile_id
        self.profile_dict = profile_dict
        self.extra_data = extra_data


    @staticmethod
    def from_json_dict(json_dict):
        return Job(json_dict["job_id"],
                   json_dict["submission_time"],
                   json_dict["job"]["resource_request"],
                   json_dict["job"]["walltime"],
                   json_dict["job"]["profile_id"],
                   json_dict.get("profile"),
                   json_dict["job"].get("extra_data"))

    #TODO: will disappear soon?
    class AllocValidationStrategy(Enum):
        MatchJobRequestExactly = 0
        MatchJobRequestBigEnough = 1

    class ExecutorPlacement:

        class ExecutorPlacementType(Enum):
            PredefinedExecutorPlacementStrategyWrapper = 0
            CustomExecutorToHostMapping = 1

        class ExecutorPlacementStrategy(Enum):
            SpreadOverHostsFirst = 0
            FillOneHostCoresFirst = 1

        def __init__(self, placement_type = ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper,
                           placement_arg = ExecutorPlacementStrategy.SpreadOverHostsFirst):
            self.placement_type = placement_type

            self.placement_strategy = placement_arg if self.placement_type is self.ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper else None
            self.custom_mapping = placement_arg if self.placement_type is self.ExecutorPlacementType.CustomExecutorToHostMapping else None

        def to_json_dict(self):
            json_dict = {
                "executor_placement_type": self.placement_type.name
            }

            if self.placement_type == self.ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper:
                json_dict["executor_placement"] = {
                    "strategy": self.placement_strategy.name
                }
            elif self.placement_type == self.ExecutorPlacementType.CustomExecutorToHostMapping:
                json_dict["executor_placement"] = {
                    "mapping": self.custom_mapping
                }
            return json_dict


# Stores all simulation parameters and information exchanged in the hello events
@dataclass
class SimulationMetadata:
    edc_init_str: str | None = None

    # Batsim and batprotocol information
    batprotocol_version: str | None = None
    batsim_version: str | None = None
    batsim_commit: str | None = None

    # TODO: consider using a enum.Flag and a single attribute
    # simulation features requested by the EDC
    dynamic_registration: bool = False
    profile_reuse: bool = False
    acknowledge_dynamic_jobs: bool = False
    forward_profiles_on_job_submission: bool = False
    forward_profiles_on_jobs_killed: bool = False
    forward_profiles_on_simulation_begins: bool = False
    forward_unknown_external_events: bool = False

    # TODO: will disappear soon?
    # scheduling constraints
    compute_sharing: bool = False
    storage_sharing: bool = True
    job_allocation_validation_strategy: Job.AllocValidationStrategy = \
            Job.AllocValidationStrategy.MatchJobRequestExactly

    def to_batsim_dict(self):
        return {
            "batprotocol_version": self.batprotocol_version, #TODO
            "requested_simulation_features": {
                "dynamic_registration": self.dynamic_registration,
                "profile_reuse": self.profile_reuse,
                "acknowledge_dynamic_jobs": self.acknowledge_dynamic_jobs,
                "forward_profiles_on_job_submission": self.forward_profiles_on_job_submission,
                "forward_profiles_on_jobs_killed": self.forward_profiles_on_jobs_killed,
                "forward_profiles_on_simulation_begins": self.forward_profiles_on_simulation_begins,
                "forward_unknown_external_events": self.forward_unknown_external_events,
            },
            "scheduling_constraints": {
                "compute_sharing": self.compute_sharing,
                "storage_sharing": self.storage_sharing,
                "job_allocation_validation_strategy": self.job_allocation_validation_strategy.name,
            },
        }


class Batsim:
    # SERIALIZATION_FORMAT_BINARY = 1  # unsupported
    SERIALIZATION_FORMAT_JSON = 2

    WORKLOAD_JOB_SEPARATOR = "!"
    #ATTEMPT_JOB_SEPARATOR = "#" # Used when resubmitting job

    def __init__(self, *, endpoint: str, timeout: int | None):
        self._endpoint: str = endpoint
        self._timeout: int = -1 if timeout is None else timeout
        self._zmq_socket: zmq.Socket | None = None

        self._edc = None

        self._time = 0
        self._received_SimulationEnds = False
        self._simulation_metadata: SimulationMetadata = SimulationMetadata()
        self._rx: deque[Event] = deque()
        self._tx: deque[Event] = deque()

    def __setup_zmq(self):
        context = zmq.Context()
        context.setsockopt(zmq.RCVTIMEO, self._timeout)

        self._zmq_socket = context.socket(socket_type=zmq.REP)

        self._zmq_socket.bind(self._endpoint)
        self._endpoint = self._zmq_socket.getsockopt(zmq.LAST_ENDPOINT) # Get the real endpoint without wilcards

    def __teardown_zmq(self):
        self._zmq_socket.unbind(self._endpoint)
        #self._zmq_socket.close()
        self._zmq_socket.context.destroy() # Closes open socket

    def __enter__(self):
        self.__setup_zmq()  # connect to Batsim ØMQ socket

        try:
            # handle init message
            self._recv_init_msg()
            self._zmq_socket.send_string("") # Batsim expects an empty answer

            # handle Batsim Hello event/message
            self._recv_batsim_hello_msg()

            return self

        except Exception:  # XXX: consider reducing caught exceptions
            self.__teardown_zmq()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.__teardown_zmq()  # always clean the Batsim ØMQ resources (context/socket)
        return False  # always propagate exceptions occurring in the with block

    @property
    def connected(self) -> bool:
        return self._zmq_socket is not None and not self._zmq_socket.closed

    @property
    def time(self):
        return self._time

    def _recv_init_msg(self) -> None:
        # Batsim sends the first message (init message)
        # Batsim waits for an empty message as an answer.
        #
        # message format:
        # 1. flags(uint32)
        # 2. data_size(uint32)
        # 3. data(data_size bytes): EDC initialization string (forwarded from Batsim CLI)

        assert self._zmq_socket is not None, "Uninitialized _zmq_socket"

        raw_msg: bytes = self._zmq_socket.recv()
        assert raw_msg is not None, "Invalid init message"

        flags = int.from_bytes(raw_msg[0:4], byteorder=sys.byteorder)
        if flags != self.SERIALIZATION_FORMAT_JSON:
            raise NotImplementedError(f"Unsupported batprotocol serialization format, expected '{self.SERIALIZATION_FORMAT_JSON}' but got '{flags}'")

        data_size = int.from_bytes(raw_msg[4:8], byteorder=sys.byteorder)
        data: bytes = raw_msg[8:]
        if len(raw_msg) != 4 + 4 + data_size:
            raise ValueError(f"Invalid data_size: received init message is {len(raw_msg)} bytes long, read data is {data_size} bytes long (should be 8 bytes less).")

        self._simulation_metadata.edc_init_str = data[:data_size].decode('utf-8')

    def _recv_batsim_hello_msg(self) -> None:
        # wait for Batsim hello message, and set simulation metadata accordingly
        self.recv_msg()
        event = self.pop_event()
        assert event.type == EventType.BatsimHelloEvent, f"Received '{event.type.name}', expected '{EventType.BatsimHelloEvent.name}'"

        metadata = self._simulation_metadata
        metadata.batprotocol_version = event.data["batprotocol_version"]
        metadata.batsim_version = event.data["batsim_version"]
        metadata.batsim_commit = event.data["batsim_commit"]

    def register_EDC(self, edc):
        self._edc = edc

        edc_hello_event = self._tx[0]

        if edc_hello_event.type != EventType.EDCHelloEvent:
            raise ValueError(f"EDC asked to send '{edc_hello_event.type.name}', expected '{EventType.EDCHelloEvent.name}'")

        if (len(self._tx) != 1):
            raise ProtocolError(f"The EDC Hello message must contain a single '{EventType.EDCHelloEvent.name}'")

        self.send_msg()


    '''def begin_simulation(self):
    # TODO: Update when SimulationBegins event is sent alone in a message
        # Wait for SimulationBegins message
        self.recv_msg()
        event = self.pop_event()

        if event.type != EventType.SimulationBeginsEvent:
            raise ValueError(f"[PYBATSIM]: Expecting SimulationBeginsEvent from Batsim, received {event.type.name}")

        # Pass it to EDC's handler
        # send to Batsim the answer message (possibly containing first decisions from EDC)
    '''

    def is_simulation_finished(self):
        # Whether the even SimulationEnds has been received yet
        return self._received_SimulationEnds

    def recv_msg(self):
        try:
            # The batprotocol currently adds a \0 at the end of each message formatted in JSON
            # Issue openned in batprotocol: https://framagit.org/batsim/batprotocol/-/issues/3
            #json_msg = self._zmq_socket.recv_json()
            raw_msg = self._zmq_socket.recv_string()
            json_msg = json.loads(raw_msg[:-1])
            print(f"Received Batsim message:\n{json_msg}")

            self._rx = self.deserialise_message(json_msg)
        # TODO handle json.loads exception and deserialisation exceptions
        except zmq.error.Again: # Timeout
            raise ValueError("[PYBATSIM]: Socket timeout reached, Batsim is not responding (maybe deadlocked)")


    def send_msg(self):
        json_msg = self.serialise_message(self._tx)
        print(f"Sending to Batsim:\n{json_msg}")
        self._zmq_socket.send_json(json_msg)
        self._tx = deque()

    def pop_event(self):
        return self._rx.popleft()

    def add_event(self, event):
        self._tx.append(event)

    '''
    All functions for serialisation/deserialisation of events from the batprotocol goes here
    '''
    def deserialise_message(self, json_msg):
        self._time = json_msg["now"]
        message = deque()
        for json_event in json_msg["events"]:
            print("--- Received event:", json_event)
            # TODO: properly deserialise the JSON event
            event = Event.from_json_dict(json_event)
            message.append(event)

            if event.type == EventType.SimulationEndsEvent:
                self._received_SimulationEnds = True
        return message

    def serialise_message(self, event_list):
        new_msg = {
            "now": self._time,
            "events": [e.to_json_dict() for e in self._tx]
        }
        return new_msg


    def create_EDCHelloEvent(self, EDC_name, EDC_version, EDC_commit):
        data_dict = self._simulation_metadata.to_batsim_dict()
        data_dict |= {
            "decision_component_name": EDC_name,
            "decision_component_version": EDC_version,
            "decision_component_commit": EDC_commit,
        }
        return Event(self._time, EventType.EDCHelloEvent, data_dict)

    def create_RejectJobEvent(self, job_id):
        return Event(self._time, EventType.RejectJobEvent,
            {
                "data": { "job_id": job_id}
            })

    def create_ExecuteJobEvent(self, job, executor_placement = None, profile_alloc_override = None, storage_placement = None):
        exec_placement = executor_placement if executor_placement is not None else Job.ExecutorPlacement()
        alloc_dict = exec_placement.to_json_dict()
        alloc_dict["host_allocation"] = str(job.allocation)

        event_dict = {
            "job_id": job.job_id,
            "allocation": alloc_dict,
        }

        #TODO: need to correctly handle optional profile_allocation_override list (by providing QoL object/methods)
        if profile_alloc_override is not None:
            event_dict["profile_allocation_override"] = profile_alloc_override

        #TODO: need to correctly handle optional storage_placement list (by providing QoL object/methods)
        if storage_placement is not None:
            event_dict["storage_placement"] = storage_placement

        return Event(self._time, EventType.ExecuteJobEvent, event_dict)


# End of class Batsim
