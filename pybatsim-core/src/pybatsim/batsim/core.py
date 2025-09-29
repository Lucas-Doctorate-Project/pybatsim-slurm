from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, FlagBoundary, auto

from .job import Job


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

    def to_protocol_dict(self):
        return {
            "batprotocol_version": self.batprotocol_version,
            "requested_simulation_features": self.requested_features.to_protocol_dict(),
        }
