"""Validate the estimators against live driveindex.com car pages that list every sale.

Data: tests/data/*.json, parsed by scripts/parse_car_page.py from public car pages fetched
2026-10-11. A page is "fully listed" when the number of sales shown equals the published
"verified auction sales" count, so every input to the published numbers is known.
"""

import json
import statistics
from datetime import date
from pathlib import Path

import pytest

from driveindex_model.estimators import (Sale, classify_signal, market_value, median_sale,
                                         percentile, typical_range)

DATA = Path(__file__).parent / "data"
FETCHED = date(2026, 10, 11)


def _load(name):
    return [c for c in json.loads((DATA / name).read_text()) if c["fully_listed"]]


SAMPLE = _load("sample_cars.json")
LABELED = _load("labeled_cars.json")
LABELS = json.loads((DATA / "labels.json").read_text())
ALL = {c["url"]: c for c in SAMPLE + LABELED}.values()


def _sales(c):
    return [Sale(date.fromisoformat(s["date"]), s["price"], s["miles"]) for s in c["listed_sales"]]


def _as_of(c):
    return date.fromisoformat(c["as_of"]) if c["as_of"] else FETCHED


@pytest.mark.parametrize("car", [c for c in ALL if c["median"]], ids=lambda c: c["name"])
def test_median_matches_exactly(car):
    assert median_sale(_sales(car)) == car["median"]


@pytest.mark.parametrize("car", [c for c in ALL if c["p25"]], ids=lambda c: c["name"])
def test_typical_range_matches_exactly(car):
    assert typical_range(_sales(car)) == (car["p25"], car["p75"])


def test_typical_range_needs_eight_sales():
    small = [c for c in ALL if c["sales_count"] < 8]
    assert small and all(c["p25"] is None for c in small)
    assert all(typical_range(_sales(c)) is None for c in small)


def test_percentile_rounds_half_up():
    xs = list(range(15))
    assert percentile(xs, 0.75) == 11  # (15-1)*0.75 = 10.5 -> 11, like Math.round


def test_single_sale_value_is_that_sale():
    singles = [c for c in ALL if c["sales_count"] == 1 and c["market_value"]]
    assert singles
    for c in singles:
        assert market_value(_sales(c), _as_of(c), c["avg_miles"]) == c["market_value"]


def _errors(cars):
    out = []
    for c in cars:
        if c["market_value"] and c["sales_count"] >= 2:
            est = market_value(_sales(c), _as_of(c), c["avg_miles"])
            out.append(abs(est / c["market_value"] - 1))
    return out


def test_market_value_fit_on_calibration_set():
    errs = _errors(SAMPLE)
    assert len(errs) >= 15
    assert statistics.median(errs) < 0.03
    assert sum(errs) / len(errs) < 0.05


def test_market_value_holdout_on_labeled_cars():
    # Out-of-sample, and these are the market's biggest movers (harder than average).
    errs = _errors(LABELED)
    assert len(errs) >= 30
    assert statistics.median(errs) < 0.10
    assert sum(e < 0.10 for e in errs) / len(errs) > 0.55


def test_classifier_agrees_with_published_labels():
    cars = [c for c in LABELED if c["url"].split("driveindex.com")[1] in LABELS]
    hits = 0
    for c in cars:
        lab = LABELS[c["url"].split("driveindex.com")[1]]
        got = classify_signal(_sales(c), FETCHED, lab["long_run_pct"] / 100,
                              typical=c["avg_miles"], min_sales=2)
        hits += got == lab["label"]
    assert len(cars) >= 30
    assert hits / len(cars) >= 0.70


def test_since_year_is_first_sale_year():
    cars = [c for c in LABELED if c["url"].split("driveindex.com")[1] in LABELS]
    match = sum(min(s["date"] for s in c["listed_sales"])[:4]
                == str(LABELS[c["url"].split("driveindex.com")[1]]["since"]) for c in cars)
    assert match / len(cars) >= 0.9
