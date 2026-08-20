"""Provider-independent Wave E statistical-validation service seams."""

from __future__ import annotations

from typing import Iterable, Protocol

from stocks_investment.domain.research_intelligence import FactorOutcomeObservation
from stocks_investment.domain.statistical_validation import (
    FactorValidationSummary,
    HypothesisTestResult,
    StatisticalValidationRun,
    ValidationCohort,
    WalkForwardWindow,
)


class ValidationCohortBuilder(Protocol):
    version: str

    def build(self, observations: Iterable[FactorOutcomeObservation]) -> tuple[ValidationCohort, ...]: ...


class FactorStatisticalValidator(Protocol):
    version: str

    def validate(
        self, run: StatisticalValidationRun, cohort: ValidationCohort
    ) -> FactorValidationSummary: ...


class MultipleTestingAdjuster(Protocol):
    version: str

    def adjust(self, results: Iterable[HypothesisTestResult]) -> tuple[HypothesisTestResult, ...]: ...


class WalkForwardValidator(Protocol):
    version: str

    def validate(self, windows: Iterable[WalkForwardWindow]) -> tuple[FactorValidationSummary, ...]: ...
