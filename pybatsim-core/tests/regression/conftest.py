import subprocess

import pytest


@pytest.fixture
def start_batsim(request, tmp_path):
    def starter(*, platform, workload, extra_options=()):
        batcmd = ('batsim', f'--platform={platform}', f'--workload={workload}')
        batcmd += extra_options
        batprocess = subprocess.Popen(batcmd, cwd=tmp_path)

        def _cleanup():
            batprocess.terminate()
            batprocess.wait()  # set returncode

        request.addfinalizer(_cleanup)
        return batprocess

    return starter
