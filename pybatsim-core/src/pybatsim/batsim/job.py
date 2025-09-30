from enum import Enum


class Job:
    # TODO(rb): add allocation attribute

    def __init__(self, job_id, resource_request,
                 walltime, profile_id, submission_time = None,
                 profile_dict = None, extra_data = None):
        # TODO(rb):
        #   - remove submission_time from ctor,
        #   - add as optional attribute
        #   - document Batsim only should modify it
        self.job_id = job_id
        self.resource_request = resource_request
        self.walltime = walltime
        self.profile_id = profile_id
        self.submission_time = submission_time
        self.profile_dict = profile_dict
        self.extra_data = extra_data

        # Value set by the EDC (for ExecuteJobEvent)
        self.allocation: ProcSet | None = None


    @classmethod
    def from_protocol_dict(cls, json_dict):
        # TODO(rb): inject submission_time after creation
        return cls(json_dict["job_id"],
                   json_dict["job"]["resource_request"],
                   json_dict["job"]["walltime"],
                   json_dict["job"]["profile_id"],
                   json_dict["submission_time"],
                   json_dict.get("profile"),
                   json_dict["job"].get("extra_data"))

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
