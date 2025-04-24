from __future__ import annotations

import sys
import zmq
import json
import logging

from collections import deque
from procset import ProcSet

from .core import SimulationMetadata
from .events import (
    Event,
    EDCHelloEvent,
    JobCompletedEvent,
    JobSubmittedEvent,
    RejectJobEvent,
    SimulationEndsEvent,
)
from .job import Job


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
        self._simulation_metadata: SimulationMetadata = SimulationMetadata()
        self._rx: deque[Event] = deque()
        self._tx: deque[Event] = deque()

        self._received_SimulationEnds: bool = False
        self._alive_jobs: dict[str, Job] = {}

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

        except Exception:  # XXX: consider reducing caught exceptions
            self.__teardown_zmq()
            raise

        else:
            return self

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
            raise ValueError(f"Invalid data_size: received init message is {len(raw_msg)} bytes long, "
                             f"read data is {data_size} bytes long (should be 4 bytes less).")

        self._simulation_metadata.edc_init_str = data[:data_size].decode('utf-8')


    def register_EDC(self, edc):
        self._edc = edc

        edc_hello_event = self._tx[0]

        if not isinstance(edc_hello_event, EDCHelloEvent):
            raise ValueError(f"EDC asked to send '{type(edc_hello_event).__name__}', expected 'EDCHelloEvent'")

        if (len(self._tx) != 1):
            raise ProtocolError(f"The EDC Hello message must contain a single 'EDCHelloEvent'")

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
        assert self._zmq_socket is not None, "Expected _zmq_socket to be initialized"

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
        assert self._edc is not None, "Expected _edc to be initialized"
        self._edc.handle_msg(self._rx)

    def send_msg(self):
        # Sends answer message to batsim
        json_msg = self.serialise_message(self._tx)
        print(f"Sending to Batsim:\n{json_msg}")
        self._zmq_socket.send_json(json_msg)
        self._tx = deque()

    def pop_event(self):
        return self._rx.popleft()

    def append_event(self, event):
        if isinstance(event, RejectJobEvent):
            # remove from alive_jobs as this is the last possible event from Batsim
            self._alive_jobs.pop(event.job.job_id)

        self._tx.append(event)

    def deserialise_event(self, protocol_dict) -> Event:
        # hacky: inject jobs in protocol_dict when relevant
        if protocol_dict['event_type'] == 'JobCompletedEvent':
            # remove from alive_jobs as this is the last possible event from Batsim
            job = self._alive_jobs.pop(protocol_dict['event']['job_id'])
            protocol_dict['__pybatsim_job'] = job

        event = Event.from_protocol_dict(protocol_dict)

        if isinstance(event, SimulationEndsEvent):
            self._received_SimulationEnds = True
        elif isinstance(event, JobSubmittedEvent):
            # TODO: handle case where job is a dynamic job and Batsim is asked to acknowledge dynamic jobs
            self._alive_jobs[event.job.job_id] = event.job

        return event

    def deserialise_message(self, protocol_dict) -> deque[Event]:
        self._time = protocol_dict["now"]

        message: deque[Event] = deque()
        for event_dict in protocol_dict["events"]:
            print("--- Received event of type", event_dict["event_type"])
            event = self.deserialise_event(event_dict)
            message.append(event)

        return message

    def serialise_message(self, event_list):
        new_msg = {
            "now": self._time,
            "events": [e.to_protocol_dict() for e in self._tx]
        }
        return new_msg
