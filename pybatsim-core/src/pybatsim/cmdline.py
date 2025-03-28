"""
    pybatsim.cmdline
    ~~~~~~~~~~~~~~~~

    Command line interface.
"""

import argparse
import collections
import inspect
import io
import json
import logging
import sys
import textwrap
import time
import importlib.util

from pathlib import Path

from pybatsim import __version__
from pybatsim.batsim.batsim import Batsim
from pybatsim.plugin import (SCHEDULER_ENTRY_POINT, find_ambiguous_scheduler_names,
    find_plugin_schedulers)


class _JsonStoreAction(argparse.Action):
    """
    Decode and store the JSON-encoded value of a single argument.

    If the argument's value starts with a '@', the path to a JSON file is
    expected.
    Otherwise, a valid JSON string is expected.
    """
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError('nargs is not allowed')
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        try:
            rawcontent = values.strip()

            if rawcontent.startswith('@'):
                # classic text stream of the file containing the options
                json_file = open(rawcontent[1:], mode='rt', encoding='utf-8')
            else:
                # encapsulate the whole JSON string in a text stream
                json_file = io.StringIO(rawcontent)

            with json_file:
                decoded_content = json.load(json_file)
                setattr(namespace, self.dest, decoded_content)

        except OSError as err:
            # raised by open()
            raise argparse.ArgumentError(
                self,
                f'unable to read \'{err.filename}\': {err.strerror.lower()}'
            ) from None
        except json.JSONDecodeError:
            # raised by json.load(), subclass of ValueError
            raise argparse.ArgumentError(self, 'invalid JSON object') from None
        except ValueError:
            # raised by open() or json.load()
            raise argparse.ArgumentError(
                self,
                'incorrect encoding (expected utf-8)'
            ) from None


class _ListSchedulersAction(argparse.Action):
    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help='list known schedulers and exit'  # pylint: disable=redefined-builtin
    ):
        super().__init__(option_strings, dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        # organize names by actual scheduler class (some names can be aliases)
        known_schedulers_by_class = collections.defaultdict(list)
        for name, cls in find_plugin_schedulers():
            known_schedulers_by_class[cls].append(name)
        # display names of scheduler in alphabetical order
        for names in known_schedulers_by_class.values():
            names.sort()
        for cls, names in known_schedulers_by_class.items():
            doc = inspect.getdoc(cls)
            doc = doc.splitlines()[0] if doc is not None else cls.__qualname__
            print(', '.join(names) + ':')
            print('  ' + doc)
        parser.exit()


def _build_parser():
    parser = argparse.ArgumentParser(
        description='Run a PyBatsim scheduler.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''\
            exit status:
              %(prog)s can exit with the following return codes:
                0  success
                1  simulation failure
                2  argument parsing error
        '''
        )
    )
    parser.add_argument(
        '--version',
        action='version',
        version=__version__,
    )
    parser.add_argument(
        '--list-schedulers',
        action=_ListSchedulersAction,
    )
    parser.add_argument(
        '-t', '--timeout',
        default=2_000,
        type=int,
        help='the timeout (in milliseconds) to wait for a Batsim answer, '
             'supply a negative value to disable '
             '(default: 2000)',
    )
    parser.add_argument(
        '-s', '--socket-endpoint',
        default='tcp://*:28000',
        help='address of Batsim socket, '
             'formatted as \'protocol://interface:port\' '
             '(default: tcp://*:28000)',
        metavar='ADDRESS',
    )
    parser.add_argument(
        '-o', '--EDC-options',
        default={},
        action=_JsonStoreAction,
        help='options forwarded to the External Decision Component (default: empty dict), '
             'either a JSON string (e.g., \'{"option": "value"}\') '
             'or a @-prefixed JSON file containing the options (e.g., \'@options.json\')',
        metavar='[@]OPTIONS',
    )

    parser.add_argument(
        'edc_name',
        #choices=sorted(set(name for name, _ in find_plugin_schedulers())),
        metavar='EDC_name',
        help='name of the External Decision Component (EDC) to run.\n'
             f'If no second argument is provided, this should match a name registered under \'{SCHEDULER_ENTRY_POINT}\' entry point. '
             f'If a filename is provided as second argument, this should match the class name of the EDC.'
    )
    parser.add_argument(
        'filename',
        default=None,
        type=Path,
        nargs='?',
        help='(optional) path to the file containing the EDC.')
    return parser


def _abort_on_ambiguous_scheduler_name(name, *, parser):
    ambiguous_names = find_ambiguous_scheduler_names()
    if name in ambiguous_names:
        errmsg = (
            f'overlapping bindings in \'{SCHEDULER_ENTRY_POINT}\' entry point, '
            'check your packaging! '
            f'\'{name}\' is defined more than once, and binds to: '
        )
        errmsg += ', '.join(ambiguous_names[name])
        parser.error(errmsg)

def _find_scheduler_class(name):
    """Lookup a scheduler by name. Return None if not found."""
    for found_name, cls in find_plugin_schedulers():
        if name == found_name:
            return cls
    raise ValueError(f'Unknown scheduler name: {name}')

def _import_EDC_from_path(EDC_name, file_path):
    # Found here: https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
    spec = importlib.util.spec_from_file_location(EDC_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[EDC_name] = module
    spec.loader.exec_module(module)
    return module


def main(args=None):
    logging.basicConfig(level=logging.INFO)

    # retrieve arguments
    parser = _build_parser()
    arguments = parser.parse_args(args)
    logging.debug(f'parsed arguments: {vars(arguments)}')

    if arguments.filename is None:
        # EDC must exist in the Entrypoint
        sched_list = sorted(set(name for name, _ in find_plugin_schedulers()))
        if arguments.edc_name not in sched_list:
            raise ValueError(f'Invalid EDC_name: {arguments.edc_name} (choose from {sched_list})')

        _abort_on_ambiguous_scheduler_name(arguments.edc_name, parser=parser)
    else:
        pass
        if not arguments.filename.is_file():
            raise ValueError(f'Invalid file name: {arguments.filename} does not exist')

        # else need to check that EDC exists in module provided by the filename
        EDC_module = _import_EDC_from_path("EDC_module", arguments.filename)
        if not hasattr(EDC_module, arguments.edc_name):
            raise ValueError(f'Invalid EDC_name: {arguments.edc_name} not found in specified file {arguments.filename}')


    with Batsim(arguments.socket_endpoint, arguments.timeout) as batsim:
        if arguments.filename is None:
            edc_cls = _find_scheduler_class(arguments.edc_name)
        else:
            edc_cls = getattr(EDC_module, arguments.edc_name)

        edc = edc_cls(batsim, options=arguments.EDC_options)

        # TODO: for the moment SimulationBeginsEvent is sent along with other events. Handle it in the main loop
        #batsim.begin_simulation()

        while not batsim.is_simulation_finished():
            batsim.receive_message()
            edc.handle_message(batsim._rx)
            batsim.send_answer_message()

        edc.finish()
    # exit with Batsim

