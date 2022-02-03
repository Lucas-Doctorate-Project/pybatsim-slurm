"""
    pybatsim.cmdline
    ~~~~~~~~~~~~~~~~

    Command line interface.
"""

import argparse
import io
import json
import logging
import sys
import textwrap
import time

from pybatsim import __version__
from pybatsim.batsim.batsim import Batsim
from pybatsim.plugin import (SCHEDULER_ENTRY_POINT, find_ambiguous_scheduler_names,
    find_plugin_schedulers)


# TODO: relocate under scheduler module?
def find_scheduler_class(name):
    """Lookup a scheduler by name. Return None if not found."""
    for found_name, cls in find_plugin_schedulers():
        if name == found_name:
            return cls
    return None


# TODO: relocate under scheduler module?
def get_scheduler_by_name(name, *, options):
    """Return an instantiated scheduler.

    Options are passed to the scheduler initializer.
    Raises if not found.
    """
    cls = find_scheduler_class(name)
    if cls is None:
        raise ValueError(f'Unknown scheduler name: {name}')
    return cls(options)


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
        '-e', '--event-socket-endpoint',
        help='address of scheduler-published events socket, '
             'formatted as \'protocol://interface:port\'',
        metavar='ADDRESS',
    )
    parser.add_argument(
        '-o', '--scheduler-options',
        default={},
        action=_JsonStoreAction,
        help='options forwarded to the scheduler (default: empty dict), '
             'either a JSON string (e.g., \'{"option": "value"}\') '
             'or a @-prefixed JSON file containing the options (e.g., \'@options.json\')',
        metavar='[@]OPTIONS',
    )
    parser.add_argument(
        'scheduler',
        choices=sorted(set(name for name, _ in find_plugin_schedulers())),
        metavar='scheduler',
        help='name of the scheduler to run '
             f'(as registered under \'{SCHEDULER_ENTRY_POINT}\' entry point)',
    )

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


def run_simulation(scheduler, *, socket_endpoint, event_socket_endpoint, timeout):
    """Instantiate the connection to Batsim and run the simulation."""
    batsim = Batsim(
        scheduler,
        network_endpoint=socket_endpoint,
        event_endpoint=event_socket_endpoint,
        timeout=timeout
    )

    tstart = time.perf_counter_ns()  # clock of highest resolution
    batsim.start()
    tend = time.perf_counter_ns()

    logging.info(f'Simulation ran {(tend - tstart) * 1e-9:e} seconds (elapsed real time)')
    logging.info(
        'jobs: ' +
        ', '.join((
            f'{batsim.nb_jobs_submitted} submitted',
            f'{batsim.nb_jobs_scheduled} scheduled',
            f'{batsim.nb_jobs_rejected} rejected',
            f'{batsim.nb_jobs_killed} killed',
            f'{len(batsim.jobs_manually_changed)} changed',
            f'{batsim.nb_jobs_timeout} timeout',
            f'{batsim.nb_jobs_successful} success',
            f'{batsim.nb_jobs_completed} complete',
        ))
    )

    # TODO: deport check to Batsim class
    if batsim.nb_jobs_submitted != \
       batsim.nb_jobs_scheduled + batsim.nb_jobs_rejected + len(batsim.jobs_manually_changed):
        sys.exit(1)


def main(args=None):
    logging.basicConfig(level=logging.INFO)

    # retrieve arguments
    parser = _build_parser()
    arguments = parser.parse_args(args)
    logging.debug(f'parsed arguments: {vars(arguments)}')

    # instantiate scheduler
    _abort_on_ambiguous_scheduler_name(arguments.scheduler, parser=parser)
    scheduler = get_scheduler_by_name(arguments.scheduler, options=arguments.scheduler_options)

    # launch simulation
    run_simulation(
        scheduler=scheduler,
        socket_endpoint=arguments.socket_endpoint,
        event_socket_endpoint=arguments.event_socket_endpoint,
        timeout=arguments.timeout,
    )
