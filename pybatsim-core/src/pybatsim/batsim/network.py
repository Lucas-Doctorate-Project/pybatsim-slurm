"""
    batsim.network
    ~~~~~~~~~~~~~~

    Handle zmq network connections.
"""
import zmq
import json
import logging


class NetworkHandler:

    def __init__(
            self,
            socket_endpoint,
            timeout=2000,
            type=zmq.REP):
        self.socket_endpoint = socket_endpoint
        self.timeout = timeout
        self.context = zmq.Context()
        self.socket = None
        self.type = type

        self.logger = logging.getLogger(__name__)

    def send(self, msg):
        self.send_string(json.dumps(msg))

    def send_string(self, msg):
        assert self.socket, "Connection not open"
        self.logger.debug("[PYBATSIM]: SEND_MSG\n {}".format(msg))
        self.socket.send_string(msg)

    def recv_binary(self, blocking=False):
        assert self.socket, "Connection not open"
        # refer to http://api.zeromq.org/4-3:zmq-setsockopt#toc41
        if blocking or self.timeout is None or self.timeout <= 0:
            # block until a message is available
            # (note that we do not use the immediate return mode with timeout == 0)
            self.socket.setsockopt(zmq.RCVTIMEO, -1)  # -1 is infinite
        else:
            self.socket.setsockopt(zmq.RCVTIMEO, self.timeout)
        try:
            msg = self.socket.recv()
        except zmq.error.Again:
            return None

        self.logger.debug('[PYBATSIM]: RECEIVED_MSG\n {}'.format(msg))
        return msg

    def recv_json(self, blocking=False):
        msg = self.recv_string(blocking=blocking)
        if msg is not None:
            msg = json.loads(msg[:-1]) # Batsim sends an extra character after the JSON message, don't know why
        return msg

    def recv_string(self, blocking=False):
        assert self.socket, "Connection not open"
        # refer to http://api.zeromq.org/4-3:zmq-setsockopt#toc41
        if blocking or self.timeout is None or self.timeout <= 0:
            # block until a message is available
            # (note that we do not use the immediate return mode with timeout == 0)
            self.socket.setsockopt(zmq.RCVTIMEO, -1)  # -1 is infinite
        else:
            self.socket.setsockopt(zmq.RCVTIMEO, self.timeout)
        try:
            msg = self.socket.recv_string()
        except zmq.error.Again:
            return None

        self.logger.debug('[PYBATSIM]: RECEIVED_MSG\n {}'.format(msg))

        return msg

    def bind(self):
        assert not self.socket, "Connection already open"
        self.socket = self.context.socket(self.type)

        self.logger.debug("[PYBATSIM]: binding to {addr}"
                  .format(addr=self.socket_endpoint))
        self.socket.bind(self.socket_endpoint)

    '''def connect(self):
        assert not self.socket, "Connection already open"
        self.socket = self.context.socket(self.type)

        self.logger.debug("[PYBATSIM]: connecting to {addr}"
                  .format(addr=self.socket_endpoint))
        self.socket.connect(self.socket_endpoint)

    def subscribe(self, pattern=b''):
        self.type = zmq.SUB
        self.connect()
        self.socket.setsockopt(zmq.SUBSCRIBE, pattern)
    '''
    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None
