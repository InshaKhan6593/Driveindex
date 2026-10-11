from datetime import date

from driveindex_model.client_math import (AUCTION_PLATFORMS, SOURCES, buy_timing_call,
                                          class_percentile, market_temperature,
                                          price_cut_pressure, value_change_12m)
from driveindex_model.estimators import Sale, classify_signal

AS_OF = date(2026, 10, 1)


def _series(prices_by_year):
    return [Sale(date(y, m, 15), p) for y, p in prices_by_year.items() for m in (3, 9)]


def test_bottomed_can_have_positive_long_run():
    # Ran up, fell, then levelled off: bottomed even though the long-run trend is positive.
    sales = _series({2015: 60_000, 2017: 80_000, 2019: 110_000, 2020: 140_000, 2021: 125_000,
                     2022: 105_000, 2023: 96_000, 2024: 95_000, 2025: 96_000, 2026: 97_000})
    assert classify_signal(sales, AS_OF, long_run=0.03) == "bottomed"


def test_appreciating_and_depreciating_and_stable():
    up = _series({2022: 100_000, 2023: 108_000, 2024: 117_000, 2025: 127_000, 2026: 138_000})
    down = _series({2022: 100_000, 2023: 92_000, 2024: 85_000, 2025: 78_000, 2026: 72_000})
    flat = _series({2022: 100_000, 2023: 101_000, 2024: 99_000, 2025: 100_500, 2026: 100_000})
    assert classify_signal(up, AS_OF, 0.08) == "appreciating"
    assert classify_signal(down, AS_OF, -0.08) == "depreciating"
    assert classify_signal(flat, AS_OF, 0.0) == "stable"
    assert classify_signal(up[:3], AS_OF, 0.08) == "insufficient"


def test_buy_timing_calls():
    assert buy_timing_call("bottomed", 0, 0.7)[0] == "Buy Now"
    assert buy_timing_call("bottomed", 0, 0.5)[0] == "Likely Entry"
    assert buy_timing_call("appreciating", 0.09, 0.5)[0] == "Buy Now (Rising Fast)"
    assert buy_timing_call("appreciating", 0.05, 0.5)[0] == "Buy Soon"
    assert buy_timing_call("depreciating")[0] == "Wait"
    assert buy_timing_call(None)[0] == "Watch"


def test_market_temperature():
    assert market_temperature(value_change_12m(110, 100)) == "Heating up"
    assert market_temperature(value_change_12m(99.5, 100)) == "Holding flat"
    assert market_temperature(value_change_12m(90, 100)) == "Cooling off"
    assert value_change_12m(100, 90, value_year_ago_at=10, latest_sale_at=5)["kind"] == "noSales"


def test_class_percentile_needs_eight_qualified_peers():
    peers = [{"price": 100_000, "sales": 10, "confidence": 0.6, "ann_ret": r / 100,
              "signal": "stable"} for r in range(-3, 7)]
    res = class_percentile(0.05, 100_000, peers)
    assert res["n"] == 10 and res["percentile"] == 85
    assert class_percentile(0.05, 100_000, peers[:7]) is None


def test_price_cut_pressure_ignores_auction_platforms():
    retail = [{"platform": "dealer", "price": 90_000, "changes": [-5_000]} for _ in range(3)]
    assert price_cut_pressure(retail)["label"] == "Price-cut pressure"
    assert price_cut_pressure([dict(l, platform="bat") for l in retail]) is None


def test_source_registry():
    assert SOURCES["bat"] == "Bring a Trailer" and SOURCES["cab"] == "Cars & Bids"
    assert "mecum" in AUCTION_PLATFORMS and "autotrader" not in AUCTION_PLATFORMS
