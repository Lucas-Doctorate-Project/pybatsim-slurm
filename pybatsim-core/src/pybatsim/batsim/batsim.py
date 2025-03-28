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


# TODO change this, just here for dev purposes
class BatsimScheduler:
    def __init__(self, simulation_context, options = None):
        pass




# Stores all simulation parameters and info passing in the Hello events
class SimulationContext:
    # Enum for the Batprotocol
    #TODO: will disappear soon?
    class JobAllocValidationStrategy(str, Enum):
        NONE = "None"
        MatchJobRequestExactly = "MatchJobRequestExactly"
        MatchJobRequestBigEnough = "MatchJobRequestBigEnough"

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
        self.job_allocation_validation_strategy = self.JobAllocValidationStrategy.MatchJobRequestExactly



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
        self._simulation_context = None
        self._edc = None
        self._time = 0
        self._received_SimulationEnds = False

        self.__zmq_resource = Batsim.__acquire_batsim(self._socket_endpoint, self._timeout)

        self._rx: list[...] = [] # TODO change any to Event when it's done
        self._tx: list[...] = [] # TODO change any to Event when it's done

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
        #init_msg = self._connection.recv()
        init_msg = self._connection.recv()
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

        if event["event_type"] != "BatsimHelloEvent":
            raise ValueError(f"[PYBATSIM]: Expecting BatsimHelloEvent from Batsim, received {event['event_type']}")

        # Retrieve simulation context info
        event_data = event["event"]
        self._simulation_context = SimulationContext(edc_init_str,
                                                     event_data["batprotocol_version"],
                                                     event_data["batsim_version"],
                                                     event_data["batsim_commit"])

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
        if (len(self._tx) != 1) and (self._tx[0]["event_type"] != "EDCHelloEvent"):
            raise ValueError(f"[PYBATSIM]: The EDC must add an EDCHello event and no other events before calling register_EDC()")

        self.send_answer_message()


    def begin_simulation(self):
        pass
        # Wait for SimulationBegin message
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
        except zmq.error.Again: # Timeout
            raise ValueError("[PYBATSIM]: Socket timeout reached, Batsim is not responding (maybe deadlocked)")

        # TODO deserialise the message
        self._time = json_msg["now"]
        self._rx = self.deserialise_message(json_msg)

    def send_answer_message(self):
        new_msg = {
            "now": self._time,
            "events": self._tx
        }
        self._connection.send_json(new_msg)
        self._tx = []

    def pop_event(self):
        return self._rx.pop(0)

    def add_event(self, event):
        pass

    '''
    All functions for serialisation/deserialisation of events from the batprotocol goes here
    '''
    def deserialise_message(self, json_msg):
        message = []
        for json_event in json_msg["events"]:
            print("--- Received event:", json_event)
            # TODO: properly deserialise the JSON event
            message.append(json_event)

            if json_event["event_type"] == "SimulationEnds":
                self._received_SimulationEnds = True
        return message



    def add_EDCHello(self, EDC_name, EDC_version, EDC_commit=None):
        self._tx.append({"timestamp": self._time,
            "event_type": "EDCHelloEvent",
            "event": {
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
        }})


# End of class Batsim
