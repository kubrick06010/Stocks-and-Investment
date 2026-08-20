"""Wave D1 deterministic thesis engine."""

from __future__ import annotations


from stocks_investment.domain.research import ResearchResult, ResearchRun
from stocks_investment.domain.research_intelligence import (
    DriverDirection,
    SourceReference,
    ThesisAssumption,
    ThesisClassification,
    ThesisDriver,
    ThesisDriverCategory,
    ThesisInvalidator,
    ThesisSnapshot,
)


class StructuredThesisEngine:
    name = "structured_thesis"
    version = "structured_thesis_v1"

    def generate(self, run: ResearchRun, result: ResearchResult) -> ThesisSnapshot:
        if result.run_id != run.id:
            raise ValueError("research result does not belong to run")
        source = SourceReference("research_result", result.id)
        factors = tuple(
            sorted(result.factor_scores, key=lambda item: (-item.weight, item.factor_name))
        )
        valid = tuple(item for item in factors if item.score is not None)
        score = (
            sum(item.score * item.weight for item in valid if item.score is not None)
            / sum(item.weight for item in valid)
            if valid and sum(item.weight for item in valid)
            else None
        )
        failed = tuple(item for item in result.criteria if item.passed is False)
        if score is None:
            classification = ThesisClassification.INSUFFICIENT_DATA
        elif failed and score < 60:
            classification = ThesisClassification.DETERIORATING
        elif failed and score >= 80:
            classification = ThesisClassification.WATCH
        elif score >= 80:
            classification = ThesisClassification.ATTRACTIVE
        elif score >= 60:
            classification = ThesisClassification.WATCH
        else:
            classification = ThesisClassification.NEUTRAL
        drivers = tuple(
            ThesisDriver(
                item.factor_name,
                _category(item.factor_name),
                DriverDirection.POSITIVE if (item.score or 0) >= 60 else DriverDirection.NEGATIVE,
                min(1.0, item.weight),
                f"{item.score:.2f}/100" if item.score is not None else "unavailable",
                source,
                item.rationale,
            )
            for item in factors
            if item.score is not None
        )
        negatives = tuple(
            ThesisDriver(
                item.criterion_name,
                ThesisDriverCategory.VALUATION,
                DriverDirection.NEGATIVE,
                0.8,
                str(item.observed),
                source,
                item.rationale,
            )
            for item in failed
        )
        assumptions = tuple(
            ThesisAssumption(
                item.factor_name, f"{item.factor_name} remains supportive", "observed", source
            )
            for item in valid
            if item.score is not None and item.score >= 70
        )
        invalidators = tuple(
            ThesisInvalidator(item.criterion_name, "criterion remains failed", "high", source)
            for item in failed
        )
        all_drivers = drivers + negatives
        summary = (
            f"{result.ticker.symbol}: {classification.value}; evidence score {score:.1f}/100"
            if score is not None
            else f"{result.ticker.symbol}: insufficient structured evidence"
        )
        return ThesisSnapshot(
            f"thesis:{result.id}:{self.version}",
            result.ticker,
            run.id,
            result.id,
            run.as_of,
            self.version,
            classification,
            summary,
            all_drivers,
            assumptions,
            invalidators,
            {"composite_score": score, "criterion_count": len(result.criteria)},
            min(1.0, len(valid) / len(factors)) if factors else None,
            None,
        )


def _category(name: str) -> ThesisDriverCategory:
    lowered = name.lower()
    for category in ThesisDriverCategory:
        if category.value in lowered:
            return category
    return ThesisDriverCategory.QUALITY
