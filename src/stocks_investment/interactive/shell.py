"""Small, read-only terminal session for persisted research inspection."""

from __future__ import annotations

import cmd
import hashlib
import json
import shlex
from datetime import date
from typing import Callable, TextIO

from stocks_investment.domain.interactive import (
    OutcomeVisibility,
    ResearchView,
    ResearchViewKind,
    ResearchViewRequest,
)
from stocks_investment.interfaces.interactive import InteractiveResearchService


Renderer = Callable[[ResearchView], str]


class InteractiveShell(cmd.Cmd):
    """A deterministic command loop over an injected read-only service.

    The shell deliberately knows neither storage nor providers.  Commands only
    construct :class:`ResearchViewRequest` values and render the returned view.
    """

    intro = "Interactive research session. Type 'help' for commands."
    prompt = "stocks> "
    methodology_version = "interactive_research_v1"
    _forbidden = frozenset(";|&<>`$")

    def __init__(
        self,
        service: InteractiveResearchService,
        renderer: Renderer,
        *,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        super().__init__(stdin=stdin, stdout=stdout)
        self.service = service
        self.renderer = renderer

    def default(self, line: str) -> None:
        self._error("unknown command")

    def parseline(self, line: str) -> tuple[str | None, str | None, str]:
        """Parse command names including the documented hyphenated names."""
        stripped = line.strip()
        if not stripped:
            return None, None, stripped
        if stripped.startswith("?"):
            stripped = "help" + stripped[1:]
        parts = stripped.split(None, 1)
        command = parts[0]
        command = {
            "thesis-history": "thesis_history",
            "filing-history": "filing_history",
        }.get(command, command)
        argument = parts[1] if len(parts) == 2 else ""
        return command, argument, stripped

    def emptyline(self) -> bool:
        return False

    def do_quit(self, line: str) -> bool:
        """quit: leave the session."""
        if line.strip():
            self._error("quit takes no arguments")
            return False
        return True

    def do_exit(self, line: str) -> bool:
        """exit: leave the session."""
        if line.strip():
            self._error("exit takes no arguments")
            return False
        return True

    def do_help(self, line: str) -> None:
        """help [command]: show the available read-only commands."""
        if line.strip():
            super().do_help(line)
            return
        self.stdout.write(
            "commands: stock, thesis-history, changes, watchlist, filing, "
            "filing-history, backtest, compare, factor, automation, "
            "construction, help, quit, exit\n"
        )

    def do_stock(self, line: str) -> None:
        self._query(ResearchViewKind.STOCK, line, "ticker")

    def do_thesis_history(self, line: str) -> None:
        self._query(ResearchViewKind.THESIS_HISTORY, line, "ticker")

    def do_changes(self, line: str) -> None:
        self._query(ResearchViewKind.CHANGES, line, "ticker")

    def do_watchlist(self, line: str) -> None:
        self._query(ResearchViewKind.WATCHLIST, line, None)

    def do_filing(self, line: str) -> None:
        self._query(ResearchViewKind.FILING, line, "ticker")

    def do_filing_history(self, line: str) -> None:
        self._query(ResearchViewKind.FILING_HISTORY, line, "ticker")

    def do_backtest(self, line: str) -> None:
        self._query(ResearchViewKind.BACKTEST, line, "backtest id")

    def do_compare(self, line: str) -> None:
        self._query(ResearchViewKind.STRATEGY_COMPARISON, line, "first backtest id", secondary=True)

    def do_factor(self, line: str) -> None:
        self._query(ResearchViewKind.FACTOR_EFFICACY, line, "factor")

    def do_automation(self, line: str) -> None:
        self._query(ResearchViewKind.AUTOMATION_RUN, line, "automation run id")

    def do_construction(self, line: str) -> None:
        self._query(ResearchViewKind.PORTFOLIO_CONSTRUCTION, line, "construction id")

    def _query(
        self,
        kind: ResearchViewKind,
        line: str,
        primary_label: str | None,
        *,
        secondary: bool = False,
    ) -> None:
        try:
            request = self._request(kind, line, primary_label, secondary=secondary)
            view = self.service.query(request)
            rendered = self.renderer(view)
            if not isinstance(rendered, str):
                raise TypeError("renderer returned non-text output")
        except (TypeError, ValueError) as exc:
            self._error(str(exc))
            return
        self.stdout.write(rendered.rstrip("\n") + "\n")

    def _request(
        self,
        kind: ResearchViewKind,
        line: str,
        primary_label: str | None,
        *,
        secondary: bool,
    ) -> ResearchViewRequest:
        if any(character in self._forbidden or ord(character) < 32 for character in line):
            raise ValueError("unsupported shell syntax")
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError as exc:
            raise ValueError("malformed command") from exc
        primary, positional, options = self._parse_tokens(tokens, primary_label, secondary)
        secondary_id = self._option_text(options.pop("__secondary", None))
        as_of = self._date_option(options.pop("as-of", None))
        outcomes = options.pop("outcomes", False)
        factor_version = self._option_text(options.pop("factor-version", None))
        horizon = self._option_text(options.pop("horizon", None))
        if options:
            raise ValueError(f"unknown option --{sorted(options)[0]}")
        if kind is ResearchViewKind.FACTOR_EFFICACY and (factor_version is None or horizon is None):
            raise ValueError("factor requires --factor-version and --horizon")
        if outcomes and kind not in {
            ResearchViewKind.STOCK,
            ResearchViewKind.BACKTEST,
            ResearchViewKind.STRATEGY_COMPARISON,
            ResearchViewKind.FACTOR_EFFICACY,
        }:
            raise ValueError("--outcomes is not valid for this command")
        if kind is not ResearchViewKind.FACTOR_EFFICACY and (factor_version or horizon):
            raise ValueError("factor options are only valid for factor")
        if kind is ResearchViewKind.WATCHLIST and primary is not None:
            raise ValueError("watchlist takes no identifier")
        if kind is ResearchViewKind.FACTOR_EFFICACY:
            primary = primary or "factor"
        if positional:
            raise ValueError("too many positional arguments")
        values = {
            "kind": kind.value,
            "primary_id": primary,
            "secondary_id": secondary_id,
            "as_of": as_of.isoformat() if as_of else None,
            "factor_version": factor_version,
            "horizon": horizon,
            "outcome_visibility": OutcomeVisibility.SEPARATE.value if outcomes else OutcomeVisibility.EXCLUDE.value,
        }
        request_id = "interactive-" + hashlib.sha256(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
        return ResearchViewRequest(
            id=request_id,
            kind=kind,
            methodology_version=self.methodology_version,
            primary_id=primary,
            secondary_id=secondary_id,
            as_of=as_of,
            factor_version=factor_version,
            horizon=horizon,
            outcome_visibility=OutcomeVisibility.SEPARATE if outcomes else OutcomeVisibility.EXCLUDE,
        )

    def _parse_tokens(
        self, tokens: list[str], primary_label: str | None, secondary: bool
    ) -> tuple[str | None, list[str], dict[str, str | bool]]:
        positional: list[str] = []
        options: dict[str, str | bool] = {}
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == "--outcomes":
                if "outcomes" in options:
                    raise ValueError("duplicate --outcomes")
                options[token[2:]] = True
            elif token.startswith("--"):
                name = token[2:]
                if name not in {"as-of", "factor-version", "horizon"} or index + 1 >= len(tokens):
                    raise ValueError(f"invalid option {token}")
                if name in options:
                    raise ValueError(f"duplicate --{name}")
                index += 1
                options[name] = self._required_text(tokens[index])
            else:
                positional.append(token)
            index += 1
        primary = self._clean_identifier(positional.pop(0)) if primary_label and positional else None
        if primary_label and primary is None:
            raise ValueError(f"missing {primary_label}")
        if secondary:
            if not positional:
                raise ValueError("missing second backtest id")
            options["__secondary"] = self._required_text(positional.pop(0))
        return primary, positional, options

    @staticmethod
    def _clean_identifier(value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("identifier must be plain text")
        return value

    @staticmethod
    def _required_text(value: str) -> str:
        cleaned = InteractiveShell._clean_identifier(value)
        if cleaned is None:
            raise ValueError("identifier must be plain text")
        return cleaned

    @staticmethod
    def _option_text(value: str | bool | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("option requires a value")
        return InteractiveShell._clean_identifier(value)

    @staticmethod
    def _date_option(value: str | bool | None) -> date | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("as-of must be YYYY-MM-DD") from exc

    def _error(self, message: str) -> None:
        self.stdout.write(f"error: {message}\n")


def run_session(
    service: InteractiveResearchService,
    renderer: Renderer,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Run one interactive session with injected dependencies."""
    InteractiveShell(service, renderer, stdin=stdin, stdout=stdout).cmdloop()
