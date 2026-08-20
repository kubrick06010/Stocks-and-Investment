from __future__ import annotations

from io import StringIO

import pytest

from stocks_investment.domain.interactive import ResearchView, ResearchViewStatus
from stocks_investment.interactive.shell import InteractiveShell


class FakeService:
    version = "fake"

    def __init__(self) -> None:
        self.requests = []

    def query(self, request):
        self.requests.append(request)
        return ResearchView(request.id, ResearchViewStatus.NOT_FOUND, None, (), ())


def make_shell() -> tuple[InteractiveShell, FakeService, StringIO]:
    service = FakeService()
    output = StringIO()
    shell = InteractiveShell(service, lambda view: f"{view.request_id}:{view.status}", stdout=output)
    return shell, service, output


def test_supported_commands_create_typed_requests() -> None:
    shell, service, output = make_shell()
    shell.onecmd("stock AAPL --as-of 2025-01-02 --outcomes")
    shell.onecmd("compare bt-a bt-b")
    shell.onecmd("factor quality --factor-version quality_v1 --horizon 12M")

    assert len(service.requests) == 3
    assert service.requests[0].primary_id == "AAPL"
    assert service.requests[0].as_of.isoformat() == "2025-01-02"
    assert service.requests[0].outcome_visibility.value == "separate"
    assert service.requests[1].secondary_id == "bt-b"
    assert service.requests[2].factor_version == "quality_v1"
    assert service.requests[2].horizon == "12M"
    assert output.getvalue()


def test_repeated_command_has_identical_request_identity() -> None:
    shell, service, _ = make_shell()
    shell.onecmd("thesis-history AAA --as-of 2024-12-31")
    shell.onecmd("thesis-history AAA --as-of 2024-12-31")
    assert service.requests[0] == service.requests[1]


@pytest.mark.parametrize("line", ["stock", "compare one", "factor quality", "factor quality --horizon 12M"])
def test_malformed_commands_do_not_call_service(line: str) -> None:
    shell, service, output = make_shell()
    shell.onecmd(line)
    assert not service.requests
    assert output.getvalue().startswith("error:")


@pytest.mark.parametrize("line", ["stock AAA; quit", "stock AAA | cat", "stock AAA $(pwd)", "stock 'AAA"])
def test_shell_escape_and_malformed_input_are_rejected(line: str) -> None:
    shell, service, output = make_shell()
    shell.onecmd(line)
    assert not service.requests
    assert "error:" in output.getvalue()


def test_mutation_and_unknown_commands_are_not_available() -> None:
    shell, service, output = make_shell()
    shell.onecmd("delete AAA")
    shell.onecmd("! ls")
    shell.onecmd("watchlist --outcomes")
    assert not service.requests
    assert output.getvalue().count("error:") == 3


def test_quit_and_exit_stop_only_without_arguments() -> None:
    shell, _, output = make_shell()
    assert shell.onecmd("quit") is True
    assert shell.onecmd("quit now") is False
    assert shell.onecmd("exit now") is False
    assert "error: quit takes no arguments" in output.getvalue()
    assert "error: exit takes no arguments" in output.getvalue()
