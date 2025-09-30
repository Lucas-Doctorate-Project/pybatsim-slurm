from enum import Enum


class Job:
    def __init__(self, job_id, resource_request,
                 walltime, profile_id, extra_data = None):
        self.job_id: str = job_id
        self.resource_request: int = resource_request
        self.walltime: float  = walltime
        self.profile_id: str = profile_id
        self.extra_data: dict | None = extra_data

        # submission_time and profile_dict are None by default
        # Only batsim should set their value (retrieved from batprotocol JobSubmittedEvent)
        self.submission_time: float | None = None
        self.profile_dict: dict | None = None

        # Value set by the EDC (for ExecuteJobEvent)
        self.allocation: ProcSet | None = None


    @classmethod
    def from_protocol_dict(cls, json_dict):
        job = cls(json_dict["job_id"],
                  json_dict["job"]["resource_request"],
                  json_dict["job"]["walltime"],
                  json_dict["job"]["profile_id"],
                  json_dict["job"].get("extra_data"))
        job.submission_time = json_dict["submission_time"]
        job.profile_dict = json_dict.get("profile")
        return job

    class ExecutorPlacement:

        class ExecutorPlacementType(Enum):
            PredefinedExecutorPlacementStrategyWrapper = 0
            CustomExecutorToHostMapping = 1

        class ExecutorPlacementStrategy(Enum):
            SpreadOverHostsFirst = 0
            FillOneHostCoresFirst = 1

        def __init__(self, placement_type = ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper,
                           placement_arg = ExecutorPlacementStrategy.SpreadOverHostsFirst):
            self.placement_type = placement_type

            self.placement_strategy = placement_arg if self.placement_type is self.ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper else None
            self.custom_mapping = placement_arg if self.placement_type is self.ExecutorPlacementType.CustomExecutorToHostMapping else None

        def to_json_dict(self):
            json_dict = {
                "executor_placement_type": self.placement_type.name
            }

            if self.placement_type == self.ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper:
                json_dict["executor_placement"] = {
                    "strategy": self.placement_strategy.name
                }
            elif self.placement_type == self.ExecutorPlacementType.CustomExecutorToHostMapping:
                json_dict["executor_placement"] = {
                    "mapping": self.custom_mapping
                }
            return json_dict


    # class PlacementPolicy
    # TODO: implement me
    # A merge of executor_placement, profile_allocation_override, storage_placement

    # class KillProgress
    # TODO: implement me
