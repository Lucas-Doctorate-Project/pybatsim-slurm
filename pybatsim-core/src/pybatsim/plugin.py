"""
    pybatsim.plugin
    ~~~~~~~~~~~~~~~

    PyBatsim plugin interface.
"""

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
