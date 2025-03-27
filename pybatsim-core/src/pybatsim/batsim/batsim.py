import json
import sys
import zmq
import logging

from enum import Enum
from procset import ProcSet

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
    def __init__(self):
        pass


class Batsim:
    WORKLOAD_JOB_SEPARATOR = "!"
    #ATTEMPT_JOB_SEPARATOR = "#" # Used when resubmitting job




    def __init__(self,
            network_endpoint,
            timeout):
        self._network_endpoint = network_endpoint

        self.ctx = zmq.Context()
        self.ctx.setsockopt(zmq.RCVTIMEO, self.timeout)
        self.socket_type = zmq.REP

        if timeout is not None:
            self._timeout = timeout
        else:
            self._timeout = -1 # Infinite timeout

        self.connected = False

    def __enter__(self):
        # Create ZMQ socket (in context manager) and connect to batsim
        self.socket = self.ctx.socket(self.socket_type)
        #self.socket.__enter__()
        self.socket.bind(self.network_endpoint) # Returns a context manager
        self.connected = True

        #Wait for BatsimHello message and retrieve simulation context info
        self.receive_message()
        event = self.pop_event()

        # if the event is not a BatsimHello event there is a problem

        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.socket.__exit__() # TODO what to do with the 3 arguments?

        self.connected = False


    def register_EDC(self, EDC):
        pass
        # Calls the BatsimHello handler of the EDC
        # send to Batsim the answer message containing EDCHello

    def begin_simulation(self):
        pass
        # Wait for SimulationBegin message
        # Pass it to EDC's handler
        # send to Batsim the answer message (possibly containing first decisions from EDC)

    def is_simulation_finished(self):
        pass
        # Whether the even SimulationEnds has been received yet

    def receive_message(self):
        if not self.connected:
            raise ValueError("TODO")

        try:
            json_msg = json.loads(self.socket.recv_string())
        except zmq.error.Again: # Timeout
            raise ValueError("Socket timeout reached, Batsim is not responding (maybe deadlocked)")

        # TODO deserialise the message
        self.message = self.deserialise(json_msg)

    def send_answer_message(self):
        pass

    def pop_event(self):
        pass

    def add_event(self, event):
        pass

    '''
    All functions for serialisation/deserialisation of events from the batprotocol goes here
    '''


# End of class Batsim
