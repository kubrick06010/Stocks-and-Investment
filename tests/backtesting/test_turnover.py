from pytest import approx

from stocks_investment.backtesting import rebalance_metrics


def test_hand_calculated_turnover_and_cost() -> None:
    # Current: AAA 50, BBB 30, CCC 20. Target: AAA 25, BBB 25,
    # CCC 0, DDD 50. Buys+sells = 25+5+20+50 = 100 notional.
    traded, turnover, cost, investable = rebalance_metrics(
        {"AAA": 50, "BBB": 30, "CCC": 20},
        {"AAA": .25, "BBB": .25, "DDD": .50},
        100, .02,
    )
    assert traded == approx(100)
    assert turnover == approx(1)
    assert cost == approx(2)
    assert investable == approx(98)


def test_partial_turnover_only_trades_replaced_security() -> None:
    traded, turnover, cost, _ = rebalance_metrics({"AAA": 50, "BBB": 50}, {"AAA": .5, "CCC": .5}, 100, .01)
    assert traded == approx(100)
    assert turnover == approx(1)
    assert cost == approx(1)
