import csv
import random

import pytest

import pybatsim.cmdline

SCHEDULE_CSV_COLUMNS = (
    'batsim_version',
    'consumed_joules',
    'makespan',
    'max_slowdown',
    'max_turnaround_time',
    'max_waiting_time',
    'mean_slowdown',
    'mean_turnaround_time',
    'mean_waiting_time',
    'nb_computing_machines',
    'nb_grouped_switches',
    'nb_jobs',
    'nb_jobs_finished',
    'nb_jobs_killed',
    'nb_jobs_rejected',
    'nb_jobs_success',
    'nb_machine_switches',
    'scheduling_time',
    'simulation_time',
    'success_rate',
    'time_computing',
    'time_idle',
    'time_sleeping',
    'time_switching_off',
    'time_switching_on',
    'time_unavailable',
)
SCHEDULE_CSV_REPRODUCIBLE_COLUMNS = tuple(
    column
    for column in SCHEDULE_CSV_COLUMNS
    # scheduling_time and simulation_time are measured and not reproducible
    if column
    not in (
        'scheduling_time',
        'simulation_time',
    )
)


def check_schedule_regression(obtained_filename, expected_filename):
    # the schedule.csv output contains measured columns that are not
    # reproducible: only check reproducible columns
    with (
        open(obtained_filename) as obtained_csv,
        open(expected_filename) as expected_csv,
    ):
        obtained_schedule = csv.DictReader(
            obtained_csv, fieldnames=SCHEDULE_CSV_COLUMNS
        )
        expected_schedule = csv.DictReader(
            expected_csv, fieldnames=SCHEDULE_CSV_COLUMNS
        )
        schedule_diff = zip(expected_schedule, obtained_schedule, strict=True)

        next(schedule_diff)  # skip header row
        for expected, obtained in schedule_diff:
            for column in SCHEDULE_CSV_REPRODUCIBLE_COLUMNS:
                assert expected[column] == obtained[column], (
                    f'schedule.csv regression: {column}'
                )


# WARNING!
# do not use '-' in platform or workload filenames: it triggers a pytest-regressions bug
@pytest.mark.parametrize('platform', ('cluster_8_nodes.xml', 'platform_4_nodes.xml'))
@pytest.mark.parametrize(
    'workload',
    (
        'delay_profile_10_jobs.json',
        'delay_profile_1_job.json',
        'delay_profile_rejected_job.json',
    ),
)
@pytest.mark.regression
def test_random(  # noqa: PLR0913
    start_batsim, shared_datadir, file_regression, tmp_path, platform, workload
):
    batsim = start_batsim(
        platform=shared_datadir / 'platforms' / platform,
        workload=shared_datadir / 'workloads' / workload,
        extra_options=('--edc-socket-str', 'tcp://localhost:28000', ''),
    )
    random.seed('**do** fix seed for reproducibility')
    pybatsim.cmdline.main(args=('random',))
    batsim.wait(timeout=5)
    assert batsim.returncode == 0

    jobs_csv_contents = (tmp_path / 'out' / 'jobs.csv').read_text()
    file_regression.check(
        contents=jobs_csv_contents,
        extension='.jobs-csv',
    )
    schedule_csv_contents = (tmp_path / 'out' / 'schedule.csv').read_text()
    file_regression.check(
        contents=schedule_csv_contents,
        extension='.schedule-csv',
        check_fn=check_schedule_regression,
    )
