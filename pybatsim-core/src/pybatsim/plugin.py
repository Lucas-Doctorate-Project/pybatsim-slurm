"""
pybatsim.plugin
~~~~~~~~~~~~~~~

PyBatsim plugin interface.

Register user-defined External Decision Component (EDC) via the entry point mechanism.

The following snippet shows how to register under the name
``yourschedulername`` the user-defined EDC :py:class:`YourScheduler`
defined in the module :py:mod:`yourscheduler`.

.. code-block:: cfg

   [pybatsim.external_decision_components]
   yourschedulername = yourscheduler:YourScheduler


Refer to the documentation of entry points of your packaging tool to
register an EDC.
"""

import collections
from importlib.metadata import entry_points

EDC_ENTRY_POINT = 'pybatsim.external_decision_components'


def find_plugin_edcs():
    """Yield the tuples (name, class) for known External Decision Component (EDC)."""
    for edc in entry_points(group=EDC_ENTRY_POINT):
        yield edc.name, edc.load()


def find_ambiguous_edc_names():
    """
    Return the dict of names bound to multiple External Decision Component (EDC).

    For each ambiguous name, the dict maps the name to the set of entry points
    values.
    """
    known_edc_names = collections.defaultdict(set)
    for edc in entry_points(group=EDC_ENTRY_POINT):
        known_edc_names[edc.name].add(edc.value)

    return {
        name: values for (name, values) in known_edc_names.items() if len(values) > 1
    }
