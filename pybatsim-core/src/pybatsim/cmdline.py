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


# TODO: correct handling of error path
def _scheduler_options(string):
    """Convert JSON-encoded scheduler options into a dict."""
    string = string.strip()
    if string.startswith('@'):
        # classic text stream of the file containing the options
        json_file = open(string[1:], mode='rt', encoding='utf-8')
    else:
        # encapsulate the whole JSON string in a text stream
        json_file = io.StringIO(string)

    with json_file:
        options = json.load(json_file)
        return options


def _build_parser():
    parser = argparse.ArgumentParser(
        description='Run a PyBatsim scheduler.',
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
        type=_scheduler_options,
        help='options forwarded to the scheduler, '
             'either a JSON string (e.g., \'{"option": "value"}\') '
             'or an @-prefixed JSON file containing the options (e.g., \'@options.json\')',
        metavar='OPTIONS',
    )
    parser.add_argument(
        'scheduler',
        help='name of the scheduler to run '
             f'(as registered under \'{SCHEDULER_ENTRY_POINT}\' entry point)',
    )

    return parser


def _abort_on_ambiguous_scheduler_name(name):
    ambiguous_names = find_ambiguous_scheduler_names()
    if name in ambiguous_names:
        print(
            f'Error in definition of \'{SCHEDULER_ENTRY_POINT}\' entry point,',
            'check your packaging!',
            f'\'{name}\' is defined more than once, and binds to:',
            ', '.join(ambiguous_names[name]),
            file=sys.stderr,
        )
        sys.exit(1)


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
    parser = _build_parser()
    arguments = parser.parse_args(args)
    # instantiate scheduler
    _abort_on_ambiguous_scheduler_name(arguments.scheduler)
    scheduler = get_scheduler_by_name(arguments.scheduler, options=arguments.scheduler_options)
    # launch simulation
    run_simulation(
        scheduler=scheduler,
        socket_endpoint=arguments.socket_endpoint,
        event_socket_endpoint=arguments.event_socket_endpoint,
        timeout=arguments.timeout,
    )
