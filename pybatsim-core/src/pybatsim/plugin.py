"""
    pybatsim.plugin
    ~~~~~~~~~~~~~~~

    PyBatsim plugin interface.
"""

import collections
import sys

# selectable entry points were introduced in Python 3.10
if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points


SCHEDULER_ENTRY_POINT = 'pybatsim.schedulers'


def find_plugin_schedulers():
    for scheduler in entry_points(group=SCHEDULER_ENTRY_POINT):
        yield scheduler.name, scheduler.load()


def find_ambiguous_scheduler_names():
    """
    Return the dict of names bound to multiple schedulers.

    For each ambiguous name, the dict maps the name to the set of entry points
    values.
    """
    known_scheduler_names = collections.defaultdict(set)
    for scheduler in entry_points(group=SCHEDULER_ENTRY_POINT):
        known_scheduler_names[scheduler.name].add(scheduler.value)
    ambiguous_scheduler_names = {
        name: values
        for (name, values) in known_scheduler_names.items()
        if len(values) > 1
    }
    return ambiguous_scheduler_names
