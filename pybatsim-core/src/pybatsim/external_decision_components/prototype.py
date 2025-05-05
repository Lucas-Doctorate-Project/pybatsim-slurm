import importlib.util
import sys
from pathlib import Path

from pybatsim.batsim import Batsim, ExternalDecisionComponent


def _load_edc_from_path(location: Path, name: str) -> type[ExternalDecisionComponent]:
    """Load the EDC class 'name' from filepath 'location'."""

    # load filepath as a module
    # see https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
    spec = importlib.util.spec_from_file_location(
        '__pybatsim_prototype_edc_pseudo_module', location
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules['__pybatsim_prototype_edc_pseudo_module'] = module
    spec.loader.exec_module(module)

    # retrieve EDC class in loaded module
    return getattr(module, name)


class PrototypeEDC(ExternalDecisionComponent):
    """
    Load an unpackaged External Decision Component from a file.

    This convenience class proxies an EDC from a file.
    It is meant for prototyping, and we strongly advise again using it!
    **Do prefer a proper package declaring pybatsim as a dependency.**

    An example package is provided in the official repository
    (https://gitlab.inria.fr/batsim/pybatsim/) in the `pybatsim-example`
    directory.

    The scheduler expects to find in the options dict the parameters:
        - EDC_file (string): the filepath (location) containing the external
          decision component;
        - EDC_class (string): the name of the class to load.

    The user is responsible for launching pybatsim in an environment where all
    dependencies are available.
    The class MUST implement the ExternalDecisionComponent protocol.
    """

    _proxied_edc: ExternalDecisionComponent

    def __init__(self, batsim: Batsim, options):
        edc_location: Path = Path(options['EDC_file'])
        edc_name: str = options['EDC_class']

        edc_cls = _load_edc_from_path(edc_location, edc_name)
        self._proxied_edc = edc_cls(batsim, options)

    # forward **all** calls to the proxied EDC
    def __getattribute__(self, name):
        edc = object.__getattribute__(self, '_proxied_edc')  # avoids infinite recursion
        return getattr(edc, name)
