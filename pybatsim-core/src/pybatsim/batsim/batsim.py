from __future__ import annotations

import json
import sys
from collections import deque
from typing import Self

import zmq

from .core import SimulationFeatures, SimulationMetadata
from .events import (
    EDCHelloEvent,
    JobSubmittedEvent,
    KillJobsEvent,
    RegisterJobEvent,
    RejectJobEvent,
    RxEvent,
    SimulationEndsEvent,
    TxEvent,
)
from .job import Job, JobId

# SERIALIZATION_FORMAT_BINARY = 1  # unsupported
SERIALIZATION_FORMAT_JSON = 2

WORKLOAD_JOB_SEPARATOR = '!'
# ATTEMPT_JOB_SEPARATOR = '#'  # unsupported, used when resubmitting jobs


# TODO: Implement public API to access SimulationMetadata
class Batsim:
    def __init__(self, *, endpoint: str, timeout: int | None = None):
        self._endpoint: str = endpoint
        self._timeout: int = -1 if timeout is None else timeout
        self._zmq_socket: zmq.Socket | None = None

        self._edc = None

        self._time: float = 0.0
        self._simulation_metadata: SimulationMetadata = SimulationMetadata()
        self._rx: deque[RxEvent] = deque()
        self._tx: deque[TxEvent] = deque()

        self._received_SimulationEnds: bool = False

        # Batsim protocol can either send a job id or a full job description.
        # The Python API abstracts this away, and only works with Job.
        # _alive_jobs and _zombie_jobs ensure each Job object lives at least as
        # long as needed: an EDC may further extend a job's life.
        # _zombie_jobs extends the life of jobs with a pending death acknowledgment.
        #
        # The state machine of jobs, as known by pybatsim, is summarized below.
        # Initial states are drawn as rectangle with single lines.
        # Final states are drawn as rectangles with double lines.
        # Other states are drawn as dashed ovals.
        #
        # States are marked with A for jobs in _alive_jobs, Z for jobs in _zombie_jobs.
        # In the 'declared' state, only dynamic jobs are known by pybatsim:
        # static jobs are created when Batsim sends a JobSubmittedEvent.
        #
        # ┌────────────┐  ┌─────────────┐
        # │ static job │  │ dynamic job │───────────┐
        # └────────────┘  └─────────────┘           │
        #        │               │                  │
        #        │            ack &&           not(ack) &&
        #        │        RegisterJob[tx]    RegisterJob[tx]
        #        │               🠇                  │
        #        │         ╭╌╌╌╌╌╌╌╌╌╌╮             │
        #        └──╴ε╶───>╎ declared ╎             │
        #                  ╎     A*   ╎             │
        #                  ╰╌╌╌╌╌╌╌╌╌╌╯             │
        #                        │                  │
        #                 JobSubmitted[rx]          │
        #                        🠇                  │
        #                  ╭╌╌╌╌╌╌╌╌╌╌╌╮            │
        #       ┌──────────╎ submitted ╎<───────────┘
        #       │          ╎     A     ╎
        #       │          ╰╌╌╌╌╌╌╌╌╌╌╌╯
        #       │                │
        # RejectJob[tx]    ExecuteJob[tx]
        #       🠇                🠇
        # ╔══════════╗      ╭╌╌╌╌╌╌╌╌╌╮                      ╭╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╮
        # ║ rejected ║      ╎ running ╎────╴KillJob[tx]╶────>╎ running,kill_received ╎
        # ╚══════════╝      ╎    A    ╎                      ╎          A,Z          ╎
        #                   ╰╌╌╌╌╌╌╌╌╌╯                      ╰╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╯
        #                        │                                       │
        #                 JobCompleted[rx]                        JobCompleted[rx]
        #                        🠇                                       🠇
        #                 ╔═════════════╗                  ╭╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╮
        #                 ║ completed_* ║──╴KillJob[tx]╶──>╎ completed_*,kill_received ╎
        #                 ╚═════════════╝                  ╎             Z             ╎
        #                                                  ╰╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╯
        #                                                                │
        #                                                         JobKillled[rx]
        #                                                                🠇
        #                                                   ╔════════════════════════╗
        #                                                   ║ completed_*,kill_acked ║
        #                                                   ╚════════════════════════╝
        self._alive_jobs: dict[JobId, Job] = {}
        self._zombie_jobs: dict[JobId, Job] = {}

    def __setup_zmq(self) -> None:
        context = zmq.Context()
        context.setsockopt(zmq.RCVTIMEO, self._timeout)

        self._zmq_socket = context.socket(socket_type=zmq.REP)
        self._zmq_socket.bind(self._endpoint)
        # Replace _endpoint with the actual endpoint in use (no wildcard).
        self._endpoint = self._zmq_socket.getsockopt(zmq.LAST_ENDPOINT)

    def __teardown_zmq(self) -> None:
        assert self._zmq_socket is not None, 'uninitialized _zmq_socket'
        self._zmq_socket.unbind(self._endpoint)
        self._zmq_socket.close()
        self._zmq_socket.context.destroy()

    def __enter__(self) -> Self:
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
    def time(self) -> float:
        return self._time

    def consume_time(self, time: float) -> None:
        assert time > 0, 'cannot go back in time'
        self._time += time

    @property
    def simulation_metadata(self) -> SimulationMetadata:
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
        # Prepare and send the first EDC message (answer to the init message)
        # message format:
        # 1. serialization_format(uint32)
        # 2. serialized message with the EDCHelloEvent
        assert self._zmq_socket is not None, 'uninitialized _zmq_socket'

        # Check _tx buffer contains a single event of type EDCHelloEvent.
        if not isinstance(self._tx[0], EDCHelloEvent):
            err_msg = (
                f"EDC asked to send '{type(self._tx[0]).__name__}', "
                "expected 'EDCHelloEvent'"
            )
            raise TypeError(err_msg)
        if len(self._tx) != 1:
            err_msg = "EDC hello message must contain a single 'EDCHelloEvent'"
            raise ValueError(err_msg)

        # Build sequence of bytes to send.
        serialization_format: bytes = SERIALIZATION_FORMAT_JSON.to_bytes(
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

    def is_simulation_finished(self) -> bool:
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

        except Exception:  # noqa: TRY203
            # TODO: handle json.loads and deserialization exceptions
            raise

    def dispatch_msg(self) -> None:
        """Trigger handling of the received message by the registered EDC."""
        assert self._edc is not None, 'uninitialized _edc'
        self._edc.handle_msg(self._rx)

    def send_msg(self) -> None:
        """Send the built answer message to Batsim."""
        protocol_dict = self.serialize_msg()
        print(f'Sending to Batsim:\n{protocol_dict}')
        self._zmq_socket.send_json(protocol_dict)
        self._tx.clear()

    def pop_event(self) -> RxEvent:
        return self._rx.popleft()

    def append_event(self, event: TxEvent) -> None:
        """Add event to the next message for Batsim."""
        if isinstance(event, RejectJobEvent):
            # Remove from _alive_jobs as RejectJobEvent is the last possible
            # event sent to Batsim.
            assert event.job.job_id not in self._zombie_jobs
            del self._alive_jobs[event.job.job_id]

        elif isinstance(event, KillJobsEvent):
            # Extend lifetime of of jobs until we receive their death acknowledgment.
            for job in event.jobs:
                self._zombie_jobs[job.job_id] = job

        elif isinstance(event, RegisterJobEvent):
            # event.job is a dynamic job created by the EDC: keep track of it.
            assert event.job.job_id not in self._alive_jobs
            self._alive_jobs[event.job.job_id] = event.job

        self._tx.append(event)

    def deserialize_event(self, protocol_dict) -> RxEvent:
        # For events only containing a job id, retrieve the corresponding Job
        # object from _alive_jobs and inject it in protocol_dict.
        # This allows RxEvent.from_protocol_dict to work with the correct objet.
        if protocol_dict['event_type'] == 'JobCompletedEvent':
            # Remove job from _alive_jobs as this is the last related event
            # received from Batsim.
            # The job may still be present in _zombie_jobs.
            job = self._alive_jobs.pop(protocol_dict['event']['job_id'])
            protocol_dict['__pybatsim_job'] = job

        elif protocol_dict['event_type'] == 'JobsKilledEvent':
            dead_jobs = []
            for job_id in protocol_dict['event']['job_ids']:
                assert job_id not in self._alive_jobs
                job = self._zombie_jobs.pop(job_id)
                dead_jobs.append(job)
            protocol_dict['__pybatsim_dead_jobs'] = dead_jobs

        event = RxEvent.from_protocol_dict(protocol_dict)

        if isinstance(event, SimulationEndsEvent):
            self._received_SimulationEnds = True

        elif isinstance(event, JobSubmittedEvent):
            # Batsim sends a full job description in a JobSubmittedEvent.
            # The described job is either static or dynamic.
            #   - in the former case, this is a new job: store it in _alive_jobs.
            #   - in the latter case, retrieve the existing job and update in place.
            new_job = event.job
            job = self._alive_jobs.setdefault(new_job.job_id, new_job)

            if job is not new_job:
                # Dynamic jobs are submitted back by Batsim only if an
                # acknowledgment is requested.
                assert (
                    SimulationFeatures.ACKNOWLEDGE_DYNAMIC_JOBS
                    in self.simulation_metadata.requested_features
                )

                # Update the existing dynamic job in place.
                assert job.submission_time is None, 'overwriting job.submission_time'
                job.submission_time = new_job.submission_time

                assert job.profile_dict is None, 'overwriting job.profile_dict'
                job.profile_dict = new_job.profile_dict

                # Reuse the existing dynamic job in the deserialized event.
                event.job = job

        return event

    def deserialize_msg(self, protocol_dict) -> None:
        self._rx.clear()  # drop previous msg

        assert self._time <= protocol_dict['now'], 'decreasing simulation time'
        self._time = protocol_dict['now']

        # Fill _rx buffer with the events received in current msg.
        for event_dict in protocol_dict['events']:
            print('--- Received event of type', event_dict['event_type'])
            event = self.deserialize_event(event_dict)
            self._rx.append(event)

    def serialize_msg(self) -> dict:
        return {
            'now': self._time,
            'events': [event.to_protocol_dict() for event in self._tx],
        }
