"""
    schedFcfs
    ~~~~~~~~~

    Simple fcfs algoritihm using the pre-defined algorithm of the new scheduler api.

"""

from pybatsim.batsim.sched.algorithms.filling import filler_sched
from pybatsim.batsim.sched.algorithms.utils import consecutive_resources_filter
from pybatsim.batsim.sched.scheduler import as_scheduler, adapt_functional_scheduler


def _func_SchedFcfs(scheduler):
    return filler_sched(
        scheduler,
        resources_filter=consecutive_resources_filter,
        abort_on_first_nonfitting=True)


SchedFcfs = adapt_functional_scheduler(
    as_scheduler()(
        _func_SchedFcfs
    )
)
