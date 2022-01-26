"""
    schedFiller
    ~~~~~~~~~~~

    Job filling algoritihm using the pre-defined algorithm of the new scheduler api.

"""

from pybatsim_functional.algorithms.filling import filler_sched
from pybatsim_functional.algorithms.utils import consecutive_resources_filter
from pybatsim_functional.scheduler import as_scheduler, adapt_functional_scheduler


def _func_SchedFiller(scheduler):
    return filler_sched(
        scheduler,
        resources_filter=consecutive_resources_filter,
        abort_on_first_nonfitting=False)


SchedFiller = adapt_functional_scheduler(
    as_scheduler()(
        _func_SchedFiller
    )
)
