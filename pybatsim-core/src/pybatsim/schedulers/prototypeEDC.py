import sys
import importlib.util

from pathlib import Path

from pybatsim.batsim import ExternalDecisionComponent


def _import_EDC_from_path(EDC_name, EDC_file):
    # Found here: https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
    spec = importlib.util.spec_from_file_location(EDC_name, EDC_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[EDC_name] = module
    spec.loader.exec_module(module)
    return module


# A wrapper to call a user-specified EDC given in option
# The option JSON dict must contain the "EDC_file" and "EDC_class" keys
class PrototypeEDC(ExternalDecisionComponent):
    def __init__(self, batsim, options):
        print(options)

        if not "EDC_file" in options:
            raise ValueError(f"Invalid call to PrototypeEDC: missing 'EDC_file' in option JSON dict")
        if not "EDC_class" in options:
            raise ValueError(f"Invalid call to PrototypeEDC: missing 'EDC_class' in option JSON dict")

        EDC_file = Path(options["EDC_file"])
        if not EDC_file.is_file():
            raise ValueError(f'Invalid EDC_file: {EDC_file} does not exist')

        EDC_name = options["EDC_class"]
        EDC_module = _import_EDC_from_path(EDC_name, EDC_file)
        if not hasattr(EDC_module, EDC_name):
            raise ValueError(f'Invalid EDC_name: {EDC_name} not found in {EDC_file}')
        edc_cls = getattr(EDC_module, EDC_name)
        self._edc = edc_cls(batsim, options)

    def __getattribute__(self, name):
        # Need to redefine getattribute and not getattr because
        # methods existing in ExternalDecisionComponent class exist in self
        # but we want to use the self._edc ones
        edc = object.__getattribute__(self, '_edc')  # avoids infinite recursion
        return getattr(edc, name)
