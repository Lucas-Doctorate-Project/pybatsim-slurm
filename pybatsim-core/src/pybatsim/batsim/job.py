from enum import Enum
from typing import TypeAlias

from procset import ProcSet

JobId: TypeAlias = str


class Job:
    # attributes defined at initialization
    job_id: JobId
    resource_request: int
    walltime: float
    profile_id: str
    extra_data: dict | None

    # attributes defined later
    submission_time: float | None = None  # set by Batsim
    profile_dict: dict | None = None  # set by Batsim
    allocation: ProcSet | None = None  # set by the EDC

    def __init__(
        self,
        job_id: JobId,
        resource_request: int,
        walltime: float,
        profile_id: str,
        extra_data: dict | None = None,
    ):
        self.job_id = job_id
        self.resource_request = resource_request
        self.walltime = walltime
        self.profile_id = profile_id
        self.extra_data = extra_data

    # TODO: nesting class is not Pythonic
    class ExecutorPlacement:
        class ExecutorPlacementType(Enum):
            PredefinedExecutorPlacementStrategyWrapper = 0
            CustomExecutorToHostMapping = 1

        class ExecutorPlacementStrategy(Enum):
            SpreadOverHostsFirst = 0
            FillOneHostCoresFirst = 1

        def __init__(
            self,
            placement_type: ExecutorPlacementType = ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper,  # noqa: E501
            placement_arg: ExecutorPlacementStrategy = ExecutorPlacementStrategy.SpreadOverHostsFirst,  # noqa: E501
        ):
            self.placement_type = placement_type

            self.placement_strategy = (
                placement_arg
                if self.placement_type
                is self.ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper
                else None
            )
            self.custom_mapping = (
                placement_arg
                if self.placement_type
                is self.ExecutorPlacementType.CustomExecutorToHostMapping
                else None
            )

        def to_json_dict(self):
            json_dict = {
                'executor_placement_type': self.placement_type.name,
            }

            if (
                self.placement_type
                == self.ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper
            ):
                assert self.placement_strategy is not None
                json_dict['executor_placement'] = {
                    'strategy': self.placement_strategy.name
                }
            elif (
                self.placement_type
                == self.ExecutorPlacementType.CustomExecutorToHostMapping
            ):
                assert self.custom_mapping is not None
                json_dict['executor_placement'] = {
                    'mapping': self.custom_mapping,
                }

            return json_dict

    # class PlacementPolicy
    # TODO: implement me
    # A merge of executor_placement, profile_allocation_override, storage_placement

    # class KillProgress
    # TODO: implement me


class FinalState(Enum):
    SUCCESS = 'COMPLETED_SUCCESSFULLY'
    FAILED = 'COMPLETED_FAILED'
    WALLTIME_REACHED = 'COMPLETED_WALLTIME_REACHED'
    KILLED = 'COMPLETED_KILLED'
    REJECTED = 'REJECTED'
