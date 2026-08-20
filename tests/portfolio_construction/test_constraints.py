import pytest

from stocks_investment.domain import PortfolioConstraint, PortfolioConstraintKind, Ticker
from stocks_investment.portfolio_construction.constraints import apply_constraints, evaluate_constraints


def constraint(kind, limit=None, scope=None):
    return PortfolioConstraint(kind, limit, f"{kind.value}_v1", scope)


def test_max_position_is_capped_and_redistributed_deterministically():
    result = apply_constraints({"AAA": .8, "BBB": .2}, (constraint(PortfolioConstraintKind.MAX_POSITION_WEIGHT, .5),))
    assert result.feasible
    assert result.weights == {"AAA": .5, "BBB": .5}
    assert result.cash_weight == 0


def test_infeasible_long_only_is_not_silently_relaxed():
    result = apply_constraints({"AAA": -.1, "BBB": 1.1}, (constraint(PortfolioConstraintKind.LONG_ONLY),))
    assert not result.feasible
    assert any("negative" in note for note in result.notes)


def test_infeasible_sector_cap_and_missing_sector_are_explicit():
    cap = constraint(PortfolioConstraintKind.MAX_SECTOR_WEIGHT, .4, "Technology")
    missing = apply_constraints({"AAA": .6, "BBB": .4}, (cap,), sector_map={"AAA": "Technology"})
    assert not missing.feasible
    assert any(item.status.value == "not_evaluated" for item in missing.evaluations)

    impossible = apply_constraints({"AAA": .7, "BBB": .3}, (cap,), sector_map={"AAA": "Technology", "BBB": "Technology"})
    assert not impossible.feasible


def test_min_cash_scales_weights_without_losing_ticker_identity():
    result = apply_constraints({Ticker("AAA"): .8, Ticker("BBB"): .4},
                               (constraint(PortfolioConstraintKind.MIN_CASH_WEIGHT, .2),))
    assert result.feasible
    assert result.weights == {"AAA": .5333333333333333, "BBB": .26666666666666666}
    assert abs(result.cash_weight - .2) < 1e-12


def test_turnover_uses_symbol_keyed_union_and_reports_violation():
    evaluations = evaluate_constraints({"AAA": .5, "CCC": .5},
                                        (constraint(PortfolioConstraintKind.MAX_TURNOVER, .2),),
                                        current_weights={"AAA": .5, "BBB": .5})
    assert evaluations[0].observed == 1.0
    assert evaluations[0].status.value == "violated"


def test_sector_cap_is_observed_with_numeric_tolerance():
    evaluations = evaluate_constraints({"AAA": .30000000001, "BBB": .69999999999},
                                        (constraint(PortfolioConstraintKind.MAX_SECTOR_WEIGHT, .3, "Tech"),),
                                        sector_map={"AAA": "Tech", "BBB": "Health"})
    assert evaluations[0].status.value == "binding"


def test_sector_only_cap_redistributes_to_uncapped_sector_without_nan():
    constraints = (
        constraint(PortfolioConstraintKind.LONG_ONLY),
        constraint(PortfolioConstraintKind.MAX_SECTOR_WEIGHT, .4, "Technology"),
    )
    result = apply_constraints(
        {"AAA": .7, "BBB": .3}, constraints,
        sector_map={"AAA": "Technology", "BBB": "Utilities"},
    )
    assert result.feasible
    assert result.weights == pytest.approx({"AAA": .4, "BBB": .6})
