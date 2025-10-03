import random

import pytest

import pybatsim.cmdline


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
    schedule_json_contents = (tmp_path / 'out' / 'schedule.json').read_text()
    file_regression.check(
        contents=schedule_json_contents,
        extension='.schedule-json',
    )
