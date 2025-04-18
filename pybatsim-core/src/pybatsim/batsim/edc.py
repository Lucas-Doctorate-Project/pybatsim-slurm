from typing import Protocol

from .batsim import Batsim


class ExternalDecisionComponent(Protocol):
    def __init__(self, batsim: Batsim, options=None): ...

    def handle_msg(self, msg) -> None: ...

    def finalize(self) -> None: ...
