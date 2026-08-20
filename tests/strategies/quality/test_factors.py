from datetime import date

import pytest

from stocks_investment.domain import AnalysisStatus, CriterionStatus
from stocks_investment.strategies.quality import (
    AltmanInputs, BeneishInputs, PiotroskiInputs, altman_z_score,
    beneish_m_score, piotroski_f_score,
)

AS_OF = date(2025, 12, 31)


def test_piotroski_is_nine_decomposable_binary_criteria() -> None:
    result = piotroski_f_score(PiotroskiInputs(
        AS_OF, net_income=120, net_income_prior=80, total_assets=1000,
        total_assets_prior=1000, operating_cash_flow=150, total_debt=200,
        total_debt_prior=250, current_assets=500, current_assets_prior=400,
        current_liabilities=200, current_liabilities_prior=200,
        shares_outstanding=100, shares_outstanding_prior=100,
        gross_margin=.42, gross_margin_prior=.40, revenue=1200, revenue_prior=1000,
    ))
    assert result.status is AnalysisStatus.VALID
    assert result.value == 9
    assert len(result.criteria) == 9
    assert all(c.status is CriterionStatus.PASS for c in result.criteria)
    assert result.version == "piotroski_f_score_v1"


def test_piotroski_missing_prior_and_zero_denominator_are_not_imputed() -> None:
    result = piotroski_f_score(PiotroskiInputs(AS_OF, net_income=10, total_assets=0))
    assert result.value is None
    assert result.status is AnalysisStatus.INSUFFICIENT_HISTORY
    assert sum(c.status is CriterionStatus.INSUFFICIENT_DATA for c in result.criteria) >= 8


def test_altman_variants_are_explicit_and_non_manufacturer_excludes_sales_term() -> None:
    x = AltmanInputs(AS_OF, working_capital=200, retained_earnings=300, ebit=100,
                     total_assets=1000, total_liabilities=500, sales=2000,
                     market_value_equity=1500, book_value_equity=1000)
    original = altman_z_score(x, variant="original_manufacturing")
    private = altman_z_score(x, variant="private_company")
    non_manufacturer = altman_z_score(x, variant="non_manufacturer")
    assert original.value == pytest.approx(1.2*.2 + 1.4*.3 + 3.3*.1 + .6*3 + 1.0*2)
    assert private.value == pytest.approx(.717*.2 + .847*.3 + 3.107*.1 + .420*2 + .998*2)
    assert non_manufacturer.value == pytest.approx(6.56*.2 + 3.26*.3 + 6.72*.1 + 1.05*2)
    assert original.version.endswith("original_manufacturing")
    with pytest.raises(ValueError):
        altman_z_score(x, variant="unknown")


def test_altman_missing_denominator_returns_structured_missing_result() -> None:
    result = altman_z_score(AltmanInputs(AS_OF, working_capital=1, total_assets=0))
    assert result.value is None
    assert result.status is AnalysisStatus.NOT_MEANINGFUL
    assert result.observations[0].value is None


def test_beneish_uses_eight_indices_and_published_coefficients() -> None:
    x = BeneishInputs(
        AS_OF, receivables=120, receivables_prior=100, revenue=1000, revenue_prior=900,
        gross_profit=400, gross_profit_prior=378, current_assets=500,
        current_assets_prior=450, ppe=300, ppe_prior=300, total_assets=1000,
        total_assets_prior=900, depreciation=30, depreciation_prior=30,
        sga=100, sga_prior=90, total_debt=200, total_debt_prior=180,
        current_liabilities=150, current_liabilities_prior=140,
        net_income=100, operating_cash_flow=80,
    )
    result = beneish_m_score(x)
    assert result.status is AnalysisStatus.VALID
    assert len(result.observations) == 8
    assert result.value is not None
    assert result.version == "beneish_m_score_v1"


def test_beneish_zero_prior_revenue_is_not_meaningful_not_infinite() -> None:
    result = beneish_m_score(BeneishInputs(AS_OF, revenue=100, revenue_prior=0))
    assert result.value is None
    assert result.status is AnalysisStatus.NOT_MEANINGFUL
    assert all(observation.value is None for observation in result.observations)
