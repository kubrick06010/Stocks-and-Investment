from stocks_investment.cli import main


def test_version_json(capsys) -> None:
    assert main(["version", "--json"]) == 0
    assert '"version"' in capsys.readouterr().out


def test_doctor(capsys) -> None:
    assert main(["doctor"]) == 0
    assert "ok" in capsys.readouterr().out
