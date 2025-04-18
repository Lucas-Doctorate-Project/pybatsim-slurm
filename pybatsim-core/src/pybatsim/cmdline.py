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
import textwrap

from . import __version__
from .batsim import Batsim, ExternalDecisionComponent
from .plugin import (
    EDC_ENTRY_POINT,
    find_ambiguous_edc_names,
    find_plugin_edcs,
)


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

    def __call__(self, _parser, namespace, values, _option_string=None):
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
                f"unable to read '{err.filename}': {err.strerror.lower()}",
            ) from None
        except json.JSONDecodeError:
            # raised by json.load(), subclass of ValueError
            raise argparse.ArgumentError(self, 'invalid JSON object') from None
        except ValueError:
            # raised by open() or json.load()
            raise argparse.ArgumentError(
                self,
                'incorrect encoding (expected utf-8)',
            ) from None


class _ListExternalDecisionComponentsAction(argparse.Action):
    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help='list known External Decision Components (EDCs) and exit',  # noqa: A002
    ):
        super().__init__(option_strings, dest, default=default, nargs=0, help=help)

    def __call__(self, parser, _namespace, _values, _option_string=None):
        # organize names by actual EDC class (some names can be aliases)
        known_edcs_by_class = collections.defaultdict(list)
        for name, cls in find_plugin_edcs():
            known_edcs_by_class[cls].append(name)
        # display names of EDC in alphabetical order
        for names in known_edcs_by_class.values():
            names.sort()
        for cls, names in known_edcs_by_class.items():
            doc = cls.__doc__
            doc = (
                inspect.cleandoc(doc).splitlines()[0]
                if doc is not None
                else cls.__qualname__
            )
            print(', '.join(names) + ':')
            print('  ' + doc)
        parser.exit()


def _build_parser():
    parser = argparse.ArgumentParser(
        description='Run a PyBatsim External Decision Component (EDC).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            exit status:
              %(prog)s can exit with the following return codes:
                0  success
                1  simulation failure
                2  argument parsing error
        """),
    )
    parser.add_argument(
        '--version',
        action='version',
        version=__version__,
    )
    parser.add_argument(
        '--list-external-decision-components',
        '--list-edcs',
        action=_ListExternalDecisionComponentsAction,
    )
    parser.add_argument(
        '-t',
        '--timeout',
        default=5_000,
        type=int,
        help=(
            'the timeout (in milliseconds) to wait for a Batsim answer, '
            'supply a negative value to disable '
            '(default: 5000)'
        ),
    )
    parser.add_argument(
        '-s',
        '--socket-endpoint',
        default='tcp://*:28000',
        help=(
            'address of Batsim socket, '
            "formatted as 'protocol://interface:port' "
            '(default: tcp://*:28000)'
        ),
        metavar='ADDRESS',
    )
    parser.add_argument(
        '-o',
        '--edc-options',
        default={},
        action=_JsonStoreAction,
        help=(
            'options forwarded to the External Decision Component '
            '(default: empty dict), '
            'either a JSON string (e.g., \'{"option": "value"}\') '
            "or a @-prefixed JSON file containing the options (e.g., '@options.json')"
        ),
        metavar='[@]OPTIONS',
    )
    parser.add_argument(
        'edc_name',
        choices=sorted({name for name, _ in find_plugin_edcs()}),
        metavar='EDC',
        help=(
            'name of the External Decision Component (EDC) to run, '
            f"as registered under '{EDC_ENTRY_POINT}' entry point"
        ),
    )
    return parser


def _abort_on_ambiguous_edc_name(name, *, parser) -> None:
    ambiguous_names = find_ambiguous_edc_names()
    if name in ambiguous_names:
        err_msg = (
            f"overlapping bindings in '{EDC_ENTRY_POINT}' entry point, "
            'check your packaging! '
            f"'{name}' is defined more than once, and binds to: "
        )
        err_msg += ', '.join(ambiguous_names[name])
        parser.error(err_msg)


def _lookup_edc_class(name) -> type[ExternalDecisionComponent]:
    """Lookup an EDC by name."""
    for found_name, cls in find_plugin_edcs():
        if name == found_name:
            return cls

    err_msg = f'unknown EDC name: {name}'
    raise LookupError(err_msg)


def main(args=None) -> None:
    logging.basicConfig(level=logging.INFO)

    # retrieve arguments
    parser = _build_parser()
    arguments = parser.parse_args(args)
    logging.debug(f'parsed arguments: {vars(arguments)}')

    # retrieve class of requested EDC
    _abort_on_ambiguous_edc_name(arguments.edc_name, parser=parser)
    edc_cls = _lookup_edc_class(arguments.edc_name)

    # TODO: handle exceptions from ØMQ
    # A ØMQ timeout usually means batsim has deadlocked/crashed
    with Batsim(
        endpoint=arguments.socket_endpoint, timeout=arguments.timeout
    ) as batsim:
        edc: ExternalDecisionComponent = edc_cls(batsim, options=arguments.edc_options)

        batsim.register_EDC(edc)

        while not batsim.is_simulation_finished():
            batsim.recv_msg()
            batsim.dispatch_msg()
            batsim.send_msg()

        edc.finalize()
