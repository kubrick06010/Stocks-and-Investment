from datetime import date, timedelta

import pytest

from stocks_investment.domain.statistical_validation import BootstrapMethod
from stocks_investment.statistical_validation.uncertainty import (
    bootstrap_confidence_interval,
    iid_bootstrap_confidence_interval,
    moving_block_bootstrap_confidence_interval,
)


def observations(*values: float) -> tuple[tuple[date, float], ...]:
    start = date(2024, 1, 1)
    return tuple((start + timedelta(days=index), value) for index, value in enumerate(values))


def test_iid_bootstrap_is_deterministic_and_returns_frozen_contract() -> None:
    interval = iid_bootstrap_confidence_interval(
        observations(1.0, 2.0, 3.0, 4.0), confidence_level=0.90, resamples=500, seed=7
    )
    repeated = iid_bootstrap_confidence_interval(
        observations(1.0, 2.0, 3.0, 4.0), confidence_level=0.90, resamples=500, seed=7
    )
    assert interval == repeated
    assert interval.method is BootstrapMethod.IID
    assert interval.estimate == 2.5
    assert interval.lower <= interval.estimate <= interval.upper
    with pytest.raises(AttributeError):
        interval.lower = 0.0  # type: ignore[misc]


def test_moving_blocks_preserve_contiguous_order_for_an_order_sensitive_statistic() -> None:
    seen: list[tuple[float, ...]] = []

    def first_last_gap(values: tuple[float, ...] | list[float]) -> float:
        sample = tuple(values)
        seen.append(sample)
        return sample[-1] - sample[0]

    result = moving_block_bootstrap_confidence_interval(
        observations(1.0, 2.0, 3.0, 4.0, 5.0),
        block_size=2,
        statistic=first_last_gap,
        confidence_level=0.80,
        resamples=20,
        seed=11,
    )
    assert result.method is BootstrapMethod.MOVING_BLOCK
    assert result.block_size == 2
    assert all(
        all(sample[index + 1] - sample[index] == 1.0 for index in (0, 2))
        for sample in seen[1:]
    )


def test_hand_checkable_two_point_mean_bootstrap() -> None:
    result = bootstrap_confidence_interval(
        observations(10.0, 20.0), confidence_level=0.95, resamples=100, seed=0
    )
    assert result.estimate == 15.0
    assert result.lower == 10.0
    assert result.upper == 20.0


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ((), "at least two"),
        (((date(2024, 1, 2), 1.0), (date(2024, 1, 1), 2.0)), "ordered"),
        (((date(2024, 1, 1), float("nan")), (date(2024, 1, 2), 2.0)), "finite"),
    ],
)
def test_invalid_samples_are_rejected(data: tuple[tuple[date, float], ...], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        iid_bootstrap_confidence_interval(data, confidence_level=0.95, resamples=20, seed=1)


def test_moving_block_configuration_is_validated() -> None:
    data = observations(1.0, 2.0, 3.0)
    with pytest.raises(ValueError, match="block_size"):
        moving_block_bootstrap_confidence_interval(
            data, block_size=0, confidence_level=0.95, resamples=20, seed=1
        )
    with pytest.raises(ValueError, match="sample size"):
        moving_block_bootstrap_confidence_interval(
            data, block_size=4, confidence_level=0.95, resamples=20, seed=1
        )
    with pytest.raises(ValueError, match="only valid"):
        bootstrap_confidence_interval(
            data,
            confidence_level=0.95,
            resamples=20,
            seed=1,
            block_size=2,
        )
