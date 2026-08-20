from datetime import date
from pytest import approx

from stocks_investment.analytics.performance import aligned_return_pairs, alpha, beta, benchmark_relative_return


def test_beta_and_alpha_join_by_date_not_position() -> None:
    portfolio = [(date(2025, 1, 1), 100.0), (date(2025, 1, 2), 110.0), (date(2025, 1, 4), 121.0)]
    benchmark = [(date(2025, 1, 1), 100.0), (date(2025, 1, 3), 105.0), (date(2025, 1, 4), 110.0)]
    pairs = aligned_return_pairs(portfolio, benchmark)
    assert pairs == ((approx(.1), approx(5 / 105)),)
    assert beta(portfolio, benchmark) is None
    assert alpha(portfolio, benchmark) is None


def test_benchmark_relative_return_uses_common_endpoints() -> None:
    portfolio = [(date(2025, 1, 1), 100.0), (date(2025, 1, 4), 121.0)]
    benchmark = [(date(2025, 1, 1), 100.0), (date(2025, 1, 3), 105.0), (date(2025, 1, 4), 110.0)]
    assert benchmark_relative_return(portfolio, benchmark) == approx(.11)


def test_beta_and_alpha_are_defined_on_aligned_periods() -> None:
    portfolio = [(date(2025, 1, 1), 100.0), (date(2025, 1, 2), 102.0), (date(2025, 1, 3), 105.0), (date(2025, 1, 4), 107.0)]
    benchmark = [(date(2025, 1, 1), 100.0), (date(2025, 1, 2), 101.0), (date(2025, 1, 3), 103.0), (date(2025, 1, 4), 104.0)]
    assert beta(portfolio, benchmark) is not None
    assert alpha(portfolio, benchmark) is not None
