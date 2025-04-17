from __future__ import annotations

import sys
import zmq
import json
import logging

from collections import deque
from dataclasses import dataclass
from enum import auto, Flag, FlagBoundary
from procset import ProcSet

from .events import *
from .job import Job

# TODO: move this outside of batsim.py
class ExternalDecisionComponent:
    def __init__(self, batsim, options = None):
        self._batsim = batsim
        self._options = options

        self._batsim.add_EDCHello("UnknownEDC", "v0.0", "")
        self._batsim.register_EDC(self)

    def handle_msg(self, msg):
        raise NotImplementedError()

    def handle_SimulationBegins(self, event):
        pass

    def finish(self):
        pass


class SimulationFeatures(Flag, boundary=FlagBoundary.STRICT):
    """
    Configuration of simulation features.

    See batprotocol::fb::EDCRequestedSimulationFeatures for reference.
    """

    DYNAMIC_REGISTRATION = auto()
    """Enable dynamic registration of jobs and profiles."""

    PROFILE_REUSE = auto()
    """Allow existing profiles to be used to register new dynamic jobs."""

    ACKNOWLEDGE_DYNAMIC_JOBS = auto()
    """Ask Batsim to emit back a JobSubmittedEvent upon creation of a dynamic job."""

    FORWARD_PROFILES_ON_JOB_SUBMISSION = auto()
    """Include profile information in JobSubmittedEvent."""

    FORWARD_PROFILES_ON_JOBS_KILLED = auto()
    """Include profile information in JobsKilledEvent."""

    FORWARD_PROFILES_ON_SIMULATION_BEGINS = auto()
    """Include profile information in SimulationBeginsEvent."""

    FORWARD_UNKNOWN_EXTERNAL_EVENTS = auto()
    """Ask Batsim to forward unkown events."""

    @classmethod
    def default(cls) -> SimulationFeatures:
        return cls(0)

    def to_protocol_dict(self) -> dict:
        return {
            'dynamic_registration': SimulationFeatures.DYNAMIC_REGISTRATION in self,
            'profile_reuse': SimulationFeatures.PROFILE_REUSE in self,
            'acknowledge_dynamic_jobs': SimulationFeatures.ACKNOWLEDGE_DYNAMIC_JOBS in self,
            'forward_profiles_on_job_submission': SimulationFeatures.FORWARD_PROFILES_ON_JOB_SUBMISSION in self,
            'forward_profiles_on_jobs_killed': SimulationFeatures.FORWARD_PROFILES_ON_JOBS_KILLED in self,
            'forward_profiles_on_simulation_begins': SimulationFeatures.FORWARD_PROFILES_ON_SIMULATION_BEGINS in self,
            'forward_unknown_external_events': SimulationFeatures.FORWARD_UNKNOWN_EXTERNAL_EVENTS in self,
        }


# Stores all simulation parameters and information exchanged in the hello events
@dataclass
class SimulationMetadata:
    edc_init_str: str | None = None

    # Batsim and batprotocol information
    batprotocol_version: str = "undefined"
    batsim_version: str | None = None
    batsim_commit: str | None = None

    # simulation features requested by the EDC
    requested_features: SimulationFeatures = SimulationFeatures.default()

    # TODO: will disappear soon?
    # scheduling constraints
    compute_sharing: bool = False
    storage_sharing: bool = True
    job_allocation_validation_strategy: Job.AllocValidationStrategy = \
            Job.AllocValidationStrategy.MatchJobRequestExactly

    def to_protocol_dict(self):
        return {
            "batprotocol_version": self.batprotocol_version, #TODO
            "requested_simulation_features": self.requested_features.to_protocol_dict(),
            "scheduling_constraints": {
                "compute_sharing": self.compute_sharing,
                "storage_sharing": self.storage_sharing,
                "job_allocation_validation_strategy": self.job_allocation_validation_strategy.name,
            },
        }


# TODO: Implement public API to access SimulationMetadata

class Batsim:
    # SERIALIZATION_FORMAT_BINARY = 1  # unsupported
    SERIALIZATION_FORMAT_JSON = 2

    WORKLOAD_JOB_SEPARATOR = "!"
    #ATTEMPT_JOB_SEPARATOR = "#" # Used when resubmitting job

    def __init__(self, *, endpoint: str, timeout: int | None = None):
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
        self._zmq_socket.close()
        self._zmq_socket.context.destroy()

    def __enter__(self):
        self.__setup_zmq()  # connect to Batsim ØMQ socket

        try:
            # handle init message
            self._recv_init_msg()

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

    @property
    def simulation_metadata(self):
        return self._simulation_metadata


    def _recv_init_msg(self) -> None:
        # Batsim sends the first message (init message)
        # message format:
        # 1. init_data_size(uint32)
        # 2. init_data(init_data_size bytes): EDC initialization string (forwarded from Batsim CLI)
        assert self._zmq_socket is not None, "Uninitialized _zmq_socket"

        raw_msg: bytes = self._zmq_socket.recv()
        assert raw_msg is not None, "Invalid init message"

        data_size = int.from_bytes(raw_msg[:4], byteorder=sys.byteorder)
        data: bytes = raw_msg[4:]
        if len(raw_msg) != 4 + data_size:
            raise ValueError(f"Invalid data_size: received init message is {len(raw_msg)} bytes long, read data is {data_size} bytes long (should be 4 bytes less).")

        self._simulation_metadata.edc_init_str = data[:data_size].decode('utf-8')


    def register_EDC(self, edc):
        self._edc = edc

        edc_hello_event = self._tx[0]

        if edc_hello_event.type != EventType.EDCHelloEvent:
            raise ValueError(f"EDC asked to send '{edc_hello_event.type.name}', expected '{EventType.EDCHelloEvent.name}'")

        if (len(self._tx) != 1):
            raise ProtocolError(f"The EDC Hello message must contain a single '{EventType.EDCHelloEvent.name}'")

        # Send message prefixed by the serialisation_flag
        flag_part = self.SERIALIZATION_FORMAT_JSON.to_bytes(4, byteorder=sys.byteorder)
        json_part = json.dumps(self.serialise_message(self._tx))
        msg = flag_part + json_part.encode()

        print(f"Sending to Batsim:\n{json_part}")
        self._zmq_socket.send(msg)
        self._tx = deque()


    def is_simulation_finished(self):
        # Whether the even SimulationEnds has been received yet
        return self._received_SimulationEnds

    def recv_msg(self) -> None:
        try:
            raw_msg = self._zmq_socket.recv_string()
            # The batprotocol currently adds a \0 at the end of each message formatted in JSON
            # Issue openned in batprotocol: https://framagit.org/batsim/batprotocol/-/issues/3
            #json_msg = self._zmq_socket.recv_json()
            json_msg = json.loads(raw_msg[:-1])
            print(f"Received Batsim message:\n{json_msg}")

            self._rx = self.deserialise_message(json_msg)
        # TODO handle json.loads exception and deserialisation exceptions
        except zmq.error.Again: # Timeout
            raise ValueError("[PYBATSIM]: Socket timeout reached, Batsim is not responding (maybe deadlocked)")

    def dispatch_msg(self) -> None:
        # Triggers message handling by registered EDC
        self._edc.handle_msg(self._rx)

    def send_msg(self):
        # Sends answer message to batsim
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
            print("--- Received event of type", json_event["event_type"])
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

# End of class Batsim
