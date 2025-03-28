import json
import sys
import zmq
import logging

from enum import Enum
from procset import ProcSet
from contextlib import contextmanager

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



# Stores all simulation parameters and info passing in the Hello events
class SimulationContext:

    def __init__(self,
            edc_init_str,
            batprotocol_version,
            batsim_version,
            batsim_commit):

        # EDC init string
        self.edc_init_str = edc_init_str

        # Batsim and Batprotocol info
        self.batprotocol_version = batprotocol_version
        self.batsim_vesrion = batsim_version
        self.batsim_commit = batsim_commit

        # Requested simu features by the EDC (default values)
        self.dynamic_registration = False
        self.profile_reuse = False
        self.acknowledge_dynamic_jobs = False
        self.forward_profiles_on_job_submission = False
        self.forward_profiles_on_jobs_killed = False
        self.forward_profiles_on_simulation_begins = False
        self.forward_unknown_external_events = False

        # Scheduling constraints #TODO: will disappear soon?
        self.compute_sharing = False
        self.storage_sharing = True
        self.job_allocation_validation_strategy = Job.AllocValidationStrategy.MatchJobRequestExactly.name


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




class Batsim:
    WORKLOAD_JOB_SEPARATOR = "!"
    #ATTEMPT_JOB_SEPARATOR = "#" # Used when resubmitting job

    @staticmethod
    @contextmanager
    def __acquire_batsim(socket_endpoint, timeout):
        # TODO document all this
        with zmq.Context() as ctx:
            ctx.setsockopt(zmq.RCVTIMEO, timeout)
            with ctx.socket(zmq.REP) as socket:
                with socket.bind(socket_endpoint):
                    yield socket



    def __init__(self,
            socket_endpoint,
            timeout):
        self._socket_endpoint = socket_endpoint
        self._timeout = -1 if timeout is None else timeout
        self._connection = None
        self._edc = None
        self._time = 0
        self._received_SimulationEnds = False

        self._simulation_context = None

        self.__zmq_resource = Batsim.__acquire_batsim(self._socket_endpoint, self._timeout)

        self._rx: list[Event] = []
        self._tx: list[Event] = []

    @property
    def connected(self):
        return self._connection is not None and not self._connection.closed

    @property
    def time(self):
        return self._time



    def __enter__(self):
        self._connection = self.__zmq_resource.__enter__()

        # Batsim sends an init message on the socket. We must read it and answer with an empty message
        # Format of the init message: flags(uint32), data_size(uint32), data(data_size bytes)
        init_msg = self._connection.recv() # TODO: correctly handle zmq.error.Again in case of a timeout here
        if init_msg is not None:
            flags = int.from_bytes(init_msg[0:4], byteorder=sys.byteorder)
            data_size = int.from_bytes(init_msg[4:8], byteorder=sys.byteorder)
            edc_init_str = init_msg[8:].decode('utf-8') # init_str contains the scheduler initialization buffer provided to Batsim command

            if flags != 2:
                raise ValueError(f"[PYBATSIM]: Pybatsim must use JSON format of the batprotocol, expected flag value '2' but got {flags}")
            if data_size != len(edc_init_str):
                raise ValueError(f"[PYBATSIM]: Internal error when reading EDC init string: Mismatch between received data_size and actual size of data (got {data_size} and {len(edc_init_str)})")

            self._connection.send_string("") # Answer message MUST be empty
        else:
            raise ValueError("[PYBATSIM]: Init message from Batsim not received.")

        #Wait for BatsimHello message and retrieve simulation context info
        self.receive_message()
        event = self.pop_event()

        if event.type != EventType.BatsimHelloEvent:
            raise ValueError(f"[PYBATSIM]: Expecting BatsimHelloEvent from Batsim, received {event.type.name}")

        # Retrieve simulation context info
        self._simulation_context = SimulationContext(edc_init_str,
                                                    event.data["batprotocol_version"],
                                                    event.data["batsim_version"],
                                                    event.data["batsim_commit"])

        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        # TODO Correctly handle end of simulation here

        self._connection.__exit__(_exc_type, _exc_value, _traceback)

        # TODO: Correctly handle exceptions
        # Should return True to suppress the exception. Returning False propagates the exception
        return False


    def register_EDC(self, EDC):
        self._edc = EDC

        # Send the EDCHello message to batsim
        if (len(self._tx) != 1) and (self._tx[0].type != EventType.EDCHelloEvent):
            raise ValueError(f"[PYBATSIM]: The EDC must add an EDCHello event and no other events before calling register_EDC()")

        self.send_answer_message()


    def begin_simulation(self):
        # Wait for SimulationBegin message
        self.receive_message()
        event = self.pop_event()

        if event.type != EventType.SimulationBeginsEvent:
            raise ValueError(f"[PYBATSIM]: Expecting SimulationBeginsEvent from Batsim, received {event.type.name}")

        # Pass it to EDC's handler
        # send to Batsim the answer message (possibly containing first decisions from EDC)

    def is_simulation_finished(self):
        # Whether the even SimulationEnds has been received yet
        return self._received_SimulationEnds

    def receive_message(self):
        try:
            # The batprotocol currently adds a \0 at the end of each message formatted in JSON
            # Issue openned in batprotocol: https://framagit.org/batsim/batprotocol/-/issues/3
            raw_msg = self._connection.recv_string()
            json_msg = json.loads(raw_msg[:-1])
            #json_msg = self._connection.recv_json()
            print(f"Received Batsim message:\n{json_msg}")

            self._rx = self.deserialise_message(json_msg)
        except zmq.error.Again: # Timeout
            raise ValueError("[PYBATSIM]: Socket timeout reached, Batsim is not responding (maybe deadlocked)")


    def send_answer_message(self):
        try:
            json_msg = self.serialise_message(self._tx)
            print(f"Sending to Batsim:\n{json_msg}")
            self._connection.send_json(json_msg)
            self._tx = []
        except zmq.error.Again: # Timeout
            raise ValueError("[PYBATSIM]: Socket timeout reached, Batsim is not responding (maybe deadlocked)")

    def pop_event(self):
        return self._rx.pop(0)

    def add_event(self, event):
        self._tx.append(event)

    '''
    All functions for serialisation/deserialisation of events from the batprotocol goes here
    '''
    def deserialise_message(self, json_msg):
        self._time = json_msg["now"]
        message = []
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


    def create_EDCHelloEvent(self, EDC_name, EDC_version, EDC_commit=None):
        return Event(self._time, EventType.EDCHelloEvent,
            {
                "batprotocol_version": self._simulation_context.batprotocol_version, #TODO
                "decision_component_name": EDC_name,
                "decision_component_version": EDC_version,
                "decision_component_commit": EDC_commit if EDC_commit is not None else "",
                "requested_simulation_features": {
                    "dynamic_registration": self._simulation_context.dynamic_registration,
                    "profile_reuse": self._simulation_context.profile_reuse,
                    "acknowledge_dynamic_jobs": self._simulation_context.acknowledge_dynamic_jobs,
                    "forward_profiles_on_job_submission": self._simulation_context.forward_profiles_on_job_submission,
                    "forward_profiles_on_jobs_killed": self._simulation_context.forward_profiles_on_jobs_killed,
                    "forward_profiles_on_simulation_begins": self._simulation_context.forward_profiles_on_simulation_begins,
                    "forward_unknown_external_events": self._simulation_context.forward_unknown_external_events},
                "scheduling_constraints": {
                    "compute_sharing": self._simulation_context.compute_sharing,
                    "storage_sharing": self._simulation_context.storage_sharing,
                    "job_allocation_validation_strategy": self._simulation_context.job_allocation_validation_strategy}
            }
        )

    def create_RejectJobEvent(self, job_id):
        return Event(self._time, EventType.RejectJobEvent,
            {
                "data": { "job_id": job_id}
            })

    def create_ExecuteJobEvent(self, job, executor_placement = None, profile_alloc_override = None, storage_placement = None):
        exec_placement = executor_placement if executor_placement is not None else Job.ExecutorPlacement()
        alloc_dict = exec_placement.to_json_dict()
        alloc_dict["host_allocation"] = str(job.allocation)

        #TODO: need to correctly handle optional profile_allocation_override list (by providing QoL object/methods)
        #TODO: need to correctly handle optional storage_placement list (by providing QoL object/methods)

        return Event(self._time, EventType.ExecuteJobEvent,
            {
                "job_id": job.job_id,
                "allocation": alloc_dict,
                "profile_allocation_override": profile_alloc_override if profile_alloc_override is not None else [],
                "storage_placement": storage_placement if storage_placement is not None else []
            })


# End of class Batsim
