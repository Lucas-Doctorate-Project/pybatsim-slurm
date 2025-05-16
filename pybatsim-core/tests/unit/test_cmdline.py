import itertools
import pathlib

import pytest

from pybatsim import cmdline


def dict_parametrize(argnames, paramsdict, indirect=False, scope=None):
    """Decorator to parametrize test functions from a (id, argvalue) dict."""
    # zip ensures id matches its argvalue
    ids, argvalues = zip(*paramsdict.items(), strict=True)
    return pytest.mark.parametrize(argnames, argvalues, indirect, ids, scope)


@pytest.fixture
def parser():
    return cmdline._build_parser()  # noqa: SLF001


@pytest.fixture(scope='session')
def scheduler_options_dir(tmp_path_factory):
    wd = tmp_path_factory.getbasetemp() / 'scheduler_options_dir'
    wd.mkdir()

    # empty configuration
    empty_file = wd / 'empty.json'
    empty_file.write_text('{}', encoding='utf-8')
    empty_file.chmod(0o444)  # read-only

    # unreadable configuration
    unreadable_file = wd / 'unreadable.json'
    unreadable_file.touch(mode=0o000)  # all rights disabled

    # invalid encoding
    invalid_encoding_file = wd / 'invalid-encoding.json'
    invalid_encoding_file.write_bytes(b'{"invalid-utf-8": "\xc3\x28"}')
    invalid_encoding_file.chmod(0o444)  # read-only

    # invalid JSON
    empty_file = wd / 'invalid-content.json'
    empty_file.write_text('{', encoding='utf-8')
    empty_file.chmod(0o444)  # read-only

    return wd


class TestArgumentsParsing:
    PARSING_ERROR_RETURN_CODE = 2

    def test_missing_positional_edc(self, parser, capsys):
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args([])
        assert excinfo.value.code == self.PARSING_ERROR_RETURN_CODE
        stderr = capsys.readouterr().err
        assert 'error: the following arguments are required: EDC' in stderr

    @dict_parametrize(
        'args',
        {
            'short': ['-x'],
            'long': ['--wrong-long'],
            'mixed': ['-x', '--wrong-long'],
        },
    )
    def test_unknown_arguments(self, parser, capsys, args):
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(args + ['random'])
        assert excinfo.value.code == self.PARSING_ERROR_RETURN_CODE
        stderr = capsys.readouterr().err
        assert ': error: unrecognized arguments:' in stderr

    @dict_parametrize(
        'args',
        {
            'event-socket-endpoint,short': ['-e'],
            'event-socket-endpoint,long': ['--event-socket-endpoint'],
        },
    )
    def test_deprecated_arguments(self, parser, capsys, args):
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(args + ['random'])
        assert excinfo.value.code == self.PARSING_ERROR_RETURN_CODE
        stderr = capsys.readouterr().err
        assert ': error: unrecognized arguments:' in stderr

    @pytest.mark.parametrize(
        'argname',
        [
            '-t',
            '--timeout',
            '-s',
            '--socket-endpoint',
            '-o',
            '--edc-options',
        ],
    )
    def test_missing_argvalue(self, parser, capsys, argname):
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args([argname])
        assert excinfo.value.code == self.PARSING_ERROR_RETURN_CODE
        stderr = capsys.readouterr().err
        assert ': error: argument ' in stderr
        assert ': expected one argument' in stderr

    @pytest.mark.parametrize(
        'timeout',
        [
            'ImNoInt',
            'NaN',
            'Inf',
            '0.1',
        ],
    )
    def test_invalid_timeout(self, parser, capsys, timeout):
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(['-t', timeout, 'random'])
        assert excinfo.value.code == self.PARSING_ERROR_RETURN_CODE
        stderr = capsys.readouterr().err
        assert ': error: argument -t/--timeout: invalid int value: ' in stderr

    def test_invalid_encoding_scheduler_options(
        self, parser, capsys, scheduler_options_dir
    ):
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(
                ['-o', f'@{scheduler_options_dir}/invalid-encoding.json', 'random']
            )
        assert excinfo.value.code == self.PARSING_ERROR_RETURN_CODE
        stderr = capsys.readouterr().err
        assert (
            ': error: argument -o/--edc-options: incorrect encoding (expected utf-8)'
            in stderr
        )

    def test_invalid_json_scheduler_options(
        self, parser, capsys, scheduler_options_dir
    ):
        for value in ('{', f'@{scheduler_options_dir}/invalid-content.json'):
            with pytest.raises(SystemExit) as excinfo:
                parser.parse_args(['-o', value, 'random'])
            assert excinfo.value.code == self.PARSING_ERROR_RETURN_CODE
            stderr = capsys.readouterr().err
            assert ': error: argument -o/--edc-options: invalid JSON object' in stderr

    def test_unreadable_scheduler_options(self, parser, capsys):
        scheduler_options_path = pathlib.Path('non-existant.json')
        assert not scheduler_options_path.exists()
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(['-o', f'@{scheduler_options_path}', 'random'])
        assert excinfo.value.code == self.PARSING_ERROR_RETURN_CODE
        stderr = capsys.readouterr().err
        assert (
            ": error: argument -o/--edc-options: unable to read 'non-existant.json': no such file or directory"
            in stderr
        )

    @pytest.mark.parametrize(
        'combination',
        itertools.product(
            ('', '-t 42_000', '--timeout 42_000'),
            ('', '-s tcp://*:42000', '--socket-endpoint tcp://*:42000'),
            # string below are formatted to inject actual path of options JSON file
            (
                '',
                '-o {{}}',
                '-o @{dir}/empty.json',
                '--edc-options {{}}',
                '--edc-options @{dir}/empty.json',
            ),
        ),
    )
    def test_valid_combinations(self, parser, combination, scheduler_options_dir):
        args = ' '.join(combination)
        args = args.format(dir=scheduler_options_dir)  # inject path
        args = args.split()  # basic tokenization
        parser.parse_args(args + ['random'])
