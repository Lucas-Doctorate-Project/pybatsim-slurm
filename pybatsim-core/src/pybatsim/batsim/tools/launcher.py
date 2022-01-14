"""
    batsim.tools.launcher
    ~~~~~~~~~~~~~~~~~~~~~

    Tools to launch pybatsim schedulers.
"""

import json
import sys
import time
from datetime import timedelta

from pybatsim.batsim.batsim import Batsim


def launch_scheduler(scheduler,
                     socket_endpoint,
                     event_socket_endpoint,
                     options,
                     timeout):

    print("Scheduler: {} ({})".format(scheduler.__class__.__name__, options))
    time_start = time.time()

    #try:
    bs = Batsim(scheduler,
                socket_endpoint,
                timeout,
                event_socket_endpoint)
    aborted = False
    # try:
    bs.start()
    # except KeyboardInterrupt:
    #     print("Aborted...")
    #     aborted = True
    time_ran = str(timedelta(seconds=time.time() - time_start))
    print("Simulation ran for: " + time_ran)
    print("Job submitted:", bs.nb_jobs_submitted,
          ", scheduled:", bs.nb_jobs_scheduled,
          ", rejected:", bs.nb_jobs_rejected,
          ", killed:", bs.nb_jobs_killed,
          ", changed:", len(bs.jobs_manually_changed),
          ", timeout:", bs.nb_jobs_timeout,
          ", success", bs.nb_jobs_successful,
          ", complete:", bs.nb_jobs_completed)

    if bs.nb_jobs_submitted != (
            bs.nb_jobs_scheduled + bs.nb_jobs_rejected +
            len(bs.jobs_manually_changed)):
        return 1
    return 1 if aborted else 0
    #except KeyboardInterrupt:
    #    print("Aborted...")
    #    return 1
    return 0
