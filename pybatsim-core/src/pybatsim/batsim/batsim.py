from __future__ import annotations

import json
import sys
from collections import deque

import zmq

from .core import SimulationMetadata
from .events import (
    EDCHelloEvent,
    JobSubmittedEvent,
    RejectJobEvent,
    RxEvent,
    SimulationEndsEvent,
    TxEvent,
)
from .job import Job


# TODO: Implement public API to access SimulationMetadata
class Batsim:
    # SERIALIZATION_FORMAT_BINARY = 1  # unsupported
    SERIALIZATION_FORMAT_JSON = 2

    WORKLOAD_JOB_SEPARATOR = '!'
    # ATTEMPT_JOB_SEPARATOR = "#" # Used when resubmitting job

    def __init__(self, *, endpoint: str, timeout: int | None = None):
        self._endpoint: str = endpoint
        self._timeout: int = -1 if timeout is None else timeout
        self._zmq_socket: zmq.Socket | None = None

        self._edc = None

        self._time = 0
        self._simulation_metadata: SimulationMetadata = SimulationMetadata()
        self._rx: deque[RxEvent] = deque()
        self._tx: deque[TxEvent] = deque()

        self._received_SimulationEnds: bool = False
        self._alive_jobs: dict[str, Job] = {}

    def __setup_zmq(self):
        context = zmq.Context()
        context.setsockopt(zmq.RCVTIMEO, self._timeout)

        self._zmq_socket = context.socket(socket_type=zmq.REP)
        self._zmq_socket.bind(self._endpoint)
        # replace _endpoint with the actual endpoint in use (no wildcard)
        self._endpoint = self._zmq_socket.getsockopt(zmq.LAST_ENDPOINT)

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
        # 2. init_data(init_data_size bytes):
        #    EDC initialization string forwarded from Batsim CLI
        assert self._zmq_socket is not None, 'uninitialized _zmq_socket'

        raw_msg: bytes = self._zmq_socket.recv()
        assert raw_msg is not None, 'invalid init message'

        data_size = int.from_bytes(raw_msg[:4], byteorder=sys.byteorder)
        data: bytes = raw_msg[4:]
        if len(raw_msg) != 4 + data_size:
            err_msg = (
                'invalid data_size: '
                f'received init message is {len(raw_msg)} bytes long, '
                f'read data is {data_size} bytes long (should be 4 bytes less)'
            )
            raise ValueError(err_msg)

        self._simulation_metadata.edc_init_str = data[:data_size].decode('utf-8')

    def _send_edc_hello_msg(self) -> None:
        # prepare and send the first EDC message (answer to the init message)
        # message format:
        # 1. serialization_format(uint32)
        # 2. serialized message with the EDCHelloEvent
        assert self._zmq_socket is not None, 'uninitialized _zmq_socket'

        # check _tx buffer contains a single event of type EDCHelloEvent
        if not isinstance(self._tx[0], EDCHelloEvent):
            err_msg = (
                f"EDC asked to send '{type(self._tx[0]).__name__}', "
                "expected 'EDCHelloEvent'"
            )
            raise TypeError(err_msg)
        if len(self._tx) != 1:
            err_msg = "EDC hello message must contain a single 'EDCHelloEvent'"
            raise ValueError(err_msg)

        # build sequence of bytes to send
        serialization_format: bytes = self.SERIALIZATION_FORMAT_JSON.to_bytes(
            4, byteorder='little'
        )
        protocol_dict: dict = self.serialize_msg()
        raw_msg: str = json.dumps(protocol_dict)
        wire_msg: bytes = serialization_format + raw_msg.encode()

        self._zmq_socket.send(wire_msg)
        self._tx.clear()

    def register_edc(self, edc) -> None:
        self._edc = edc
        # XXX:
        #   This sequence is fragile as it requires:
        #   1. the EDC to append the hello event during its initialization
        #   2. no other creation of messages before registering
        #
        #   Consider introducing a required method craft_hello_event on
        #   ExternalDecisionComponent.
        self._send_edc_hello_msg()

    def is_simulation_finished(self):
        # Whether the even SimulationEnds has been received yet
        return self._received_SimulationEnds

    def recv_msg(self) -> None:
        assert self._zmq_socket is not None, 'uninitialized _zmq_socket'

        try:
            raw_msg = self._zmq_socket.recv_string()
            # XXX: https://framagit.org/batsim/batprotocol/-/issues/3
            #   The batprotocol appends a null byte after each sent JSON message.
            #   Consider removing the null byte from the protocol as ØMQ handles
            #   the length of sent messages.
            #   This would allow to use self._zmq_socket.recv_json()
            protocol_dict = json.loads(raw_msg[:-1])  # drop terminating null byte
            print(f'Received Batsim message: {protocol_dict}')
            self.deserialize_msg(protocol_dict)

        except Exception:
            # TODO: handle json.loads and deserialization exceptions
            raise

    def dispatch_msg(self) -> None:
        """Trigger handling of the received message by the registered EDC."""
        assert self._edc is not None, 'uninitialized _edc'
        self._edc.handle_msg(self._rx)

    def send_msg(self):
        """Send the built answer message to Batsim."""
        protocol_dict = self.serialize_msg()
        print(f'Sending to Batsim:\n{protocol_dict}')
        self._zmq_socket.send_json(protocol_dict)
        self._tx.clear()

    def pop_event(self) -> RxEvent:
        return self._rx.popleft()

    def append_event(self, event: TxEvent):
        """Add event to the next message for Batsim."""
        if isinstance(event, RejectJobEvent):
            # remove from alive_jobs as this is the last possible event sent to Batsim
            self._alive_jobs.pop(event.job.job_id)

        self._tx.append(event)

    def deserialize_event(self, protocol_dict) -> RxEvent:
        # hacky: inject jobs in protocol_dict when relevant
        if protocol_dict['event_type'] == 'JobCompletedEvent':
            # remove from alive_jobs as this is the last possible event from Batsim
            job = self._alive_jobs.pop(protocol_dict['event']['job_id'])
            protocol_dict['__pybatsim_job'] = job

        event = RxEvent.from_protocol_dict(protocol_dict)

        if isinstance(event, SimulationEndsEvent):
            self._received_SimulationEnds = True
        elif isinstance(event, JobSubmittedEvent):
            # TODO: handle case where job is a dynamic job and Batsim is asked
            # to acknowledge dynamic jobs
            self._alive_jobs[event.job.job_id] = event.job

        return event

    def deserialize_msg(self, protocol_dict) -> None:
        self._rx.clear()  # drop previous msg

        assert self._time <= protocol_dict['now'], 'decreasing simulation time'
        self._time = protocol_dict['now']

        # fill _rx buffer with the events received in current msg
        for event_dict in protocol_dict['events']:
            print('--- Received event of type', event_dict['event_type'])
            event = self.deserialize_event(event_dict)
            self._rx.append(event)

    def serialize_msg(self) -> dict:
        return {
            'now': self._time,
            'events': [event.to_protocol_dict() for event in self._tx],
        }
