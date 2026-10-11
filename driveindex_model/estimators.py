"""Server-side statistics.

Part A reproduces the public car-page numbers exactly as defined on
https://driveindex.com/methodology (rules quoted in docstrings).

Part B reconstructs what is NOT shipped to the browser: the market-value estimator and the
Value Signal inputs (annual_return, recent_return, confidence, signal). DriveIndex computes these
on its servers; the bundle only receives the results via /api/cars/<id>. Part B is built from
the published description plus the client-side constants and is an informed reconstruction,
not recovered code. Its tunable constants are marked ASSUMPTION.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, timedelta

from .client_math import mileage_adjust


@dataclass
class Sale:
    sold: date
    price: float              # USD
    miles: float | None = None
    usd: bool = True
    reserve_not_met: bool = False
    outlier: bool = False
    damage: bool = False      # accident / salvage on vehicle report
    non_us: bool = False

    @property
    def clean(self) -> bool:
        return not (self.reserve_not_met or self.outlier or self.damage or self.non_us)


def _clean_usd(sales):
    return [s for s in sales if s.clean and s.usd]


def percentile(xs: list[float], q: float) -> float:
    """Linear-interpolation percentile (q in 0..1). DriveIndex does not state its method."""
    xs = sorted(xs)
    if not xs:
        raise ValueError("no data")
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


# ---------------------------------------------------------------------------
# Part A: published, verifiable statistics
# ---------------------------------------------------------------------------

def median_sale(sales) -> float:
    """'Median sale: the middle verified USD sale for that model-year.'"""
    return statistics.median(s.price for s in _clean_usd(sales))


def typical_range(sales) -> tuple[float, float] | None:
    """'Typical range: the 25th to 75th percentile of verified USD sales, shown once a car has
    eight or more.'"""
    px = [s.price for s in _clean_usd(sales)]
    if len(px) < 8:
        return None
    return percentile(px, 0.25), percentile(px, 0.75)


def price_history_by_year(sales) -> dict[int, tuple[float, int]]:
    """'The median of the verified sales recorded in each calendar year, for years with three or
    more.'"""
    by_year: dict[int, list[float]] = {}
    for s in _clean_usd(sales):
        by_year.setdefault(s.sold.year, []).append(s.price)
    return {y: (statistics.median(v), len(v)) for y, v in sorted(by_year.items(), reverse=True)
            if len(v) >= 3}


def twelve_month_change(sales, as_of: date) -> tuple[float, str] | None:
    """'The median of the past 12 months against the prior 12, each needing at least three sales;
    when the prior year is thin the comparison base widens to one to three years ago.'"""
    clean = _clean_usd(sales)
    yr = timedelta(days=365)
    cur = [s.price for s in clean if as_of - yr < s.sold <= as_of]
    if len(cur) < 3:
        return None
    prior = [s.price for s in clean if as_of - 2 * yr < s.sold <= as_of - yr]
    basis = "prior 12 months"
    if len(prior) < 3:
        prior = [s.price for s in clean if as_of - 3 * yr < s.sold <= as_of - yr]
        basis = "1-3 years ago"
        if len(prior) < 3:
            return None
    return (statistics.median(cur) / statistics.median(prior) - 1) * 100, basis


def flag_outliers(sales, k: float = 3.0) -> None:
    """'Prices far outside the model's own distribution are excluded.' ASSUMPTION: a log-price
    MAD rule with k=3; DriveIndex does not publish its threshold."""
    px = [math.log(s.price) for s in sales if not s.reserve_not_met and s.price > 0]
    if len(px) < 5:
        return
    med = statistics.median(px)
    mad = statistics.median(abs(p - med) for p in px) or 1e-9
    for s in sales:
        if s.price > 0 and abs(math.log(s.price) - med) / (1.4826 * mad) > k:
            s.outlier = True


# ---------------------------------------------------------------------------
# Part B: reconstructions of server-side logic
# ---------------------------------------------------------------------------

def normalize_to_typical_mileage(sale: Sale, typical_miles: float, collect_score=None,
                                 age=None) -> float:
    """Invert the client's mileage curve: express a sale at the model's typical mileage.
    The client uses the same curve in the other direction (value -> specific odometer)."""
    if not sale.miles or not typical_miles:
        return sale.price
    unit = mileage_adjust(1_000_000, sale.miles, typical_miles, collect_score, age) / 1_000_000
    return sale.price / unit if unit > 0 else sale.price


def market_value(sales, as_of: date, half_life_days: float = 365.0, recent_n_boost: int = 5,
                 collect_score=None, age=None) -> float | None:
    """'Sold prices are first normalised to the model's typical mileage ... then weighted toward
    the most recent sales ... and bounded so that one unusual result cannot drag the value.'

    ASSUMPTIONS: exponential recency decay (half_life_days), double weight for the last
    `recent_n_boost` sales ("weight the last few sales most heavily"), and a weighted median
    bounded to the clean P25..P75 band (the "bounded" step).
    """
    clean = [s for s in _clean_usd(sales) if s.sold <= as_of]
    if len(clean) < 3:
        return None  # 'Limited Data'
    miles = [s.miles for s in clean if s.miles]
    typical = statistics.median(miles) if miles else None
    clean.sort(key=lambda s: s.sold, reverse=True)
    pts = []
    for i, s in enumerate(clean):
        w = 0.5 ** ((as_of - s.sold).days / half_life_days)
        if i < recent_n_boost:
            w *= 2
        pts.append((normalize_to_typical_mileage(s, typical, collect_score, age), w))
    pts.sort()
    half, acc, wmed = sum(w for _, w in pts) / 2, 0.0, pts[-1][0]
    for v, w in pts:
        acc += w
        if acc >= half:
            wmed = v
            break
    if len(clean) >= 8:
        lo, hi = percentile([v for v, _ in pts], 0.25), percentile([v for v, _ in pts], 0.75)
        wmed = min(hi, max(lo, wmed))
    return round(wmed)


@dataclass
class TrendFit:
    annual_return: float     # long-run log-linear slope -> %/yr
    recent_return: float | None
    r2: float
    cv: float
    n: int
    confidence: float
    signal: str


def value_signal(sales, as_of: date, collect_score=None, age=None) -> TrendFit | None:
    """Value Signal reconstruction: OLS of log(mileage-normalised price) on time.

    The client feeds `annual_return`, `recent_return`, `confidence` and `signal` into the
    projection engine and the market-trends pages rank by '%/yr since the first US sale', which is
    exactly an annualised log-linear slope. ASSUMPTIONS: the classification thresholds below
    and the confidence formula (sample-capped, per the methodology: 'a thin history can never
    produce a high-confidence call').
    """
    clean = [s for s in _clean_usd(sales) if s.sold <= as_of]
    if len(clean) < 5:
        return None
    miles = [s.miles for s in clean if s.miles]
    typical = statistics.median(miles) if miles else None
    xs = [(s.sold - as_of).days / 365.25 for s in clean]
    ys = [math.log(normalize_to_typical_mileage(s, typical, collect_score, age)) for s in clean]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs) or 1e-9
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    ss_tot = sum((y - my) ** 2 for y in ys) or 1e-9
    ss_res = sum((y - (my + slope * (x - mx))) ** 2 for x, y in zip(xs, ys))
    r2 = max(0.0, 1 - ss_res / ss_tot)
    prices = [math.exp(y) for y in ys]
    cv = statistics.pstdev(prices) / statistics.mean(prices)
    ann = math.exp(slope) - 1

    ch = twelve_month_change(clean, as_of)
    recent = ch[0] / 100 if ch else None

    size_cap = 0.3 if n < 8 else 0.5 if n < 15 else 0.7 if n < 25 else 0.9
    confidence = min(size_cap, 0.5 * r2 + 0.3 * min(1, n / 40) + 0.2 * max(0, 1 - cv / 0.5))

    signal = classify_signal(clean, as_of, ann, typical, collect_score, age)
    return TrendFit(ann, recent, r2, cv, n, round(confidence, 3), signal)


def _yearly_values(sales, typical, collect_score, age):
    by_year: dict[int, list[float]] = {}
    for s in sales:
        by_year.setdefault(s.sold.year, []).append(
            normalize_to_typical_mileage(s, typical, collect_score, age))
    return [(y, statistics.median(v)) for y, v in sorted(by_year.items()) if len(v) >= 2]


def _slope(points) -> float:
    """Annualised log-linear slope of (year, value) points."""
    if len(points) < 2:
        return 0.0
    xs = [p[0] for p in points]
    ys = [math.log(p[1]) for p in points]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs) or 1e-9
    return math.exp(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx) - 1


def classify_signal(sales, as_of, long_run, typical=None, collect_score=None, age=None,
                    min_sales: int = 5, drawdown_min: float = 0.12, move: float = 0.04) -> str:
    """Value Signal reconstruction from the published definitions:

      * bottomed     "verified sales show the fall has levelled off"
      * approaching  "the decline is slowing"
      * appreciating / depreciating / stable on the recent trend

    Evidence the label is NOT the long-run trend: /depreciation lists 2015 McLaren P1 as
    Bottomed at +1.6%/yr long-run and 1987 Porsche 959 as Bottomed at +5.4%/yr. So "bottomed"
    means drawn down from a peak and now flat. The client also receives `peakPrice` and
    `fromPeak` per car, which fits that. ASSUMPTIONS: thresholds `drawdown_min` (12% off peak),
    `move` (+/-4%/yr), "slowing" = decline rate down by at least a third, the 3-year recent
    window and the year-median smoothing. Calibrate against the published mix (latest recompute: 538 appreciating, 5,395 stable, 427 bottomed,
    506 depreciating, approaching not stated).
    """
    if len(sales) < min_sales:
        return "insufficient"
    yearly = _yearly_values(sales, typical, collect_score, age)
    if len(yearly) < 2:
        return "stable" if abs(long_run) < move else ("appreciating" if long_run > 0 else "depreciating")
    peak = max(v for _, v in yearly)
    last = yearly[-1][1]
    drawdown = 1 - last / peak
    recent = [p for p in yearly if p[0] >= as_of.year - 3]
    prev = [p for p in yearly if as_of.year - 6 <= p[0] < as_of.year - 2]
    r_now, r_prev = _slope(recent), _slope(prev)

    if drawdown >= drawdown_min and r_now > -move / 2 and r_prev < -move:
        return "bottomed"
    if drawdown >= drawdown_min and r_now < -move / 2 and r_now > (2 / 3) * r_prev:
        return "approaching"
    if r_now >= move:
        return "appreciating"
    if r_now <= -move:
        return "depreciating"
    return "stable"
