from enum import Enum


class Profile:

    class ProfileType(Enum):
        DelayProfile = 0
        ParallelTaskProfile = 1
        ParallelTaskHomogeneousProfile = 2
        SequentialCompositionProfile = 3
        ForkJoinCompositionProfile = 4
        ParallelTaskMergeCompositionProfile = 5
        ParallelTaskOnStorageHomogeneousProfile = 6
        ParallelTaskDataStagingBetweenStoragesProfile = 7
        TraceReplayProfile = 8


    def __init__(self, profile_id, profile_type,
                 profile_dict, extra_data = None):
        self.profile_id = profile_id
        self.profile_type = profile_type
        self.profile_dict = profile_dict
        # TODO: enhance profile creation for each type?
        self.extra_data = extra_data

    @classmethod
    def from_protocol_dict(cls, json_dict):
        return cls(json_dict['id'],
                   Profile.ProfileType[json_dict['profile_type']],
                   json_dict['profile'],
                   json_dict.get('extra_data'),
        )

