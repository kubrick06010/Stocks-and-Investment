"""Generic screening orchestration over frozen universe and scoring contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Iterable, Mapping, Protocol

from stocks_investment.domain.research import ResearchResult, ResearchRun, ResearchRunStatus
from stocks_investment.domain.research_engine import (
    CompositeScore,
    CriterionResult,
    CriterionStatus,
    FactorObservation,
    FactorScore,
    MissingDataPolicy,
    UniverseSnapshot,
)
from stocks_investment.domain.models import Ticker
from stocks_investment.interfaces.protocols import ResearchStorageBackend


class ScreeningFilter(Protocol):
    """A pure, deterministic candidate filter.

    Returning a ``CriterionResult`` retains an explainable decision; returning
    ``bool`` is supported for small adapters and is normalized by the engine.
    """

    def __call__(
        self, ticker: Ticker, observations: tuple[FactorObservation, ...]
    ) -> bool | CriterionResult: ...


@dataclass(frozen=True, slots=True)
class Candidate:
    """All score and criterion inputs for one universe member."""

    ticker: Ticker
    composite_score: CompositeScore | None = None
    observations: tuple[FactorObservation, ...] = ()
    criteria: tuple[CriterionResult, ...] = ()


@dataclass(frozen=True, slots=True)
class ScreeningSelection:
    ticker: Ticker
    rank: int | None
    composite_score: float | None
    status: str
    criteria: tuple[CriterionResult, ...] = ()
    observations: tuple[FactorObservation, ...] = ()
    factor_scores: tuple[FactorScore, ...] = ()


@dataclass(frozen=True, slots=True)
class ScreeningRun:
    """The in-memory result of a screening pass, including audit metadata."""

    run: ResearchRun
    universe: UniverseSnapshot
    selections: tuple[ScreeningSelection, ...]


@dataclass(frozen=True, slots=True)
class ScreeningEngine:
    """Apply filters and rank supplied C1-C3 outputs deterministically."""

    storage: ResearchStorageBackend | None = None

    def run(
        self,
        universe: UniverseSnapshot,
        candidates: Mapping[str, Candidate] | Iterable[Candidate],
        *,
        strategy_name: str,
        strategy_version: str,
        parameters: Mapping[str, object] | None = None,
        filters: Iterable[ScreeningFilter] = (),
        missing_data_policy: MissingDataPolicy = MissingDataPolicy.INSUFFICIENT_DATA,
        data_snapshot: str | None = None,
        run_id: str | None = None,
        created_at: datetime | None = None,
        git_commit: str | None = None,
        persist: bool = True,
    ) -> ScreeningRun:
        """Screen a dated universe and optionally persist its Research records.

        Inputs are never fetched or recomputed here.  Missing composite scores
        and non-valid scores are retained as unranked selections, while
        ``FAIL``/``INSUFFICIENT_DATA`` policies prevent them from passing an
        implicit score requirement. Explicit filters remain authoritative.
        """
        candidate_map = self._candidate_map(candidates)
        filter_list = tuple(filters)
        selection_rows: list[tuple[Candidate, bool, tuple[CriterionResult, ...]]] = []
        for ticker in universe.members:
            candidate = candidate_map.get(ticker.symbol, Candidate(ticker=ticker))
            decisions = list(candidate.criteria)
            included = all(
                criterion.status not in (CriterionStatus.FAIL, CriterionStatus.INSUFFICIENT_DATA)
                and criterion.passed is not False
                for criterion in decisions
            )
            for screening_filter in filter_list:
                decision = screening_filter(ticker, candidate.observations)
                criterion = self._criterion_for_filter(decision, screening_filter)
                decisions.append(criterion)
                if criterion.status is CriterionStatus.FAIL or criterion.passed is False:
                    included = False
                elif criterion.status is CriterionStatus.INSUFFICIENT_DATA:
                    included = False
            if candidate.composite_score is None and missing_data_policy in (
                MissingDataPolicy.FAIL,
                MissingDataPolicy.INSUFFICIENT_DATA,
            ):
                included = False
            elif candidate.composite_score is not None and candidate.composite_score.final_score is None:
                included = False
            selection_rows.append((candidate, included, tuple(decisions)))

        included_rows = [row for row in selection_rows if row[1]]
        included_rows.sort(key=self._ranking_key)
        ranks = {candidate.ticker.symbol: index for index, (candidate, _, _) in enumerate(included_rows, 1)}
        selections = tuple(
            ScreeningSelection(
                ticker=candidate.ticker,
                rank=ranks.get(candidate.ticker.symbol),
                composite_score=self._score(candidate),
                status="selected" if included else self._excluded_status(candidate, missing_data_policy),
                criteria=criteria,
                observations=candidate.observations,
                factor_scores=(candidate.composite_score.factor_components
                               if candidate.composite_score is not None else ()),
            )
            for candidate, included, criteria in selection_rows
        )

        now = created_at or datetime.now(timezone.utc)
        effective_parameters = dict(parameters or {})
        effective_parameters.update(
            {
                "universe_version": universe.version,
                "universe_as_of": universe.as_of.isoformat(),
                "missing_data_policy": missing_data_policy.value,
                "weights": self._weights(selection_rows),
            }
        )
        effective_run_id = run_id or self._run_id(
            universe, strategy_name, strategy_version, effective_parameters, data_snapshot
        )
        research_run = ResearchRun(
            id=effective_run_id,
            created_at=now,
            as_of=universe.as_of,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            universe_name=universe.name,
            universe_version=universe.version,
            universe_as_of=universe.as_of,
            parameters=effective_parameters,
            git_commit=git_commit,
            data_snapshot=data_snapshot,
            status=ResearchRunStatus.COMPLETED,
        )
        result = ScreeningRun(research_run, universe, selections)
        if persist and self.storage is not None:
            self._persist(result)
        return result

    @staticmethod
    def _candidate_map(candidates: Mapping[str, Candidate] | Iterable[Candidate]) -> dict[str, Candidate]:
        if isinstance(candidates, Mapping):
            return {key: value for key, value in candidates.items()}
        return {candidate.ticker.symbol: candidate for candidate in candidates}

    @staticmethod
    def _score(candidate: Candidate) -> float | None:
        return candidate.composite_score.final_score if candidate.composite_score else None

    @classmethod
    def _ranking_key(cls, row: tuple[Candidate, bool, tuple[CriterionResult, ...]]) -> tuple[bool, float, str]:
        candidate = row[0]
        score = cls._score(candidate)
        return (score is None, -(score if score is not None else 0.0), candidate.ticker.symbol)

    @staticmethod
    def _criterion_for_filter(decision: bool | CriterionResult, screening_filter: ScreeningFilter) -> CriterionResult:
        if isinstance(decision, CriterionResult):
            return decision
        name = getattr(screening_filter, "name", screening_filter.__class__.__name__)
        status = CriterionStatus.PASS if decision else CriterionStatus.FAIL
        return CriterionResult(str(name), "callable_v1", None, None, status, decision, "filter result")

    @staticmethod
    def _excluded_status(candidate: Candidate, policy: MissingDataPolicy) -> str:
        if candidate.composite_score is None or candidate.composite_score.final_score is None:
            return "insufficient_data" if policy is MissingDataPolicy.INSUFFICIENT_DATA else "excluded"
        return "filtered"

    @staticmethod
    def _weights(rows: Iterable[tuple[Candidate, bool, tuple[CriterionResult, ...]]]) -> dict[str, float]:
        for candidate, _, _ in rows:
            if candidate.composite_score is not None:
                return dict(candidate.composite_score.weights)
        return {}

    def _persist(self, result: ScreeningRun) -> None:
        assert self.storage is not None
        save_universe = getattr(self.storage, "save_universe_snapshot", None)
        if save_universe is not None:
            save_universe(result.universe)
        self.storage.save_research_run(result.run)
        for selection in result.selections:
            result_id = f"{result.run.id}:{selection.ticker.symbol}"
            self.storage.save_research_result(
                ResearchResult(
                    id=result_id,
                    run_id=result.run.id,
                    ticker=selection.ticker,
                    created_at=result.run.created_at,
                    rank=selection.rank,
                    composite_score=selection.composite_score,
                    classification=selection.status,
                    factor_scores=selection.factor_scores,
                    criteria=selection.criteria,
                )
            )

    @staticmethod
    def _run_id(
        universe: UniverseSnapshot,
        strategy_name: str,
        strategy_version: str,
        parameters: Mapping[str, object],
        data_snapshot: str | None,
    ) -> str:
        payload = json.dumps(
            {
                "strategy": [strategy_name, strategy_version],
                "universe": [universe.name, universe.version, universe.as_of.isoformat(), [t.symbol for t in universe.members]],
                "parameters": parameters,
                "data_snapshot": data_snapshot,
            },
            sort_keys=True,
            default=str,
        ).encode()
        return "screen-" + hashlib.sha256(payload).hexdigest()[:24]
