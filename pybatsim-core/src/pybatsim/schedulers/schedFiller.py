"""
    schedFiller
    ~~~~~~~~~~~

    Job filling algoritihm using the pre-defined algorithm of the new scheduler api.

"""

from pybatsim.batsim.sched.algorithms.filling import filler_sched
from pybatsim.batsim.sched.algorithms.utils import consecutive_resources_filter


def SchedFiller(scheduler):
    return filler_sched(
        scheduler,
        resources_filter=consecutive_resources_filter,
        abort_on_first_nonfitting=False)
