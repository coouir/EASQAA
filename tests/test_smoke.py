import pytest

import sarqa
from sarqa.cli import main


def test_version():
    assert sarqa.__version__


def test_cli_version_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "sarqa" in capsys.readouterr().out
