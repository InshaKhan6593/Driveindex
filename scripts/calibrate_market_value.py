"""Fit the market-value estimator to cars whose public page lists every sale.

Usage: python -I scripts/calibrate_market_value.py cars.json
`cars.json` comes from parse_car_page.py.
"""

import itertools
import json
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driveindex_model.client_math import collectibility, mileage_adjust  # noqa: E402

FETCHED = date(2026, 10, 11)


def car_inputs(c):
    slug = c["url"].rstrip("/").split("/")
    make_slug, year = slug[-3], int(slug[-1])
    make = {"porsche": "Porsche", "ferrari": "Ferrari", "ford": "Ford",
            "chevrolet": "Chevrolet"}.get(make_slug, make_slug.title())
    model = c["name"].split(" ", 2)[2] if c["name"].count(" ") >= 2 else c["name"]
    return make, model, year


def _pct(xs, q):
    xs = sorted(xs)
    return xs[math.floor((len(xs) - 1) * q + 0.5)]


def fence_filter(sales, fence):
    """Drop sales far outside the car's own distribution."""
    if fence is None or len(sales) < 4:
        return sales
    px = [s["price"] for s in sales]
    if fence.startswith("iqr"):
        k = float(fence[3:])
        q1, q3 = _pct(px, 0.25), _pct(px, 0.75)
        lo, hi = q1 - k * (q3 - q1), q3 + k * (q3 - q1)
    else:  # ratio to median
        k = float(fence[5:])
        med = _pct(px, 0.5)
        lo, hi = med / k, med * k
    kept = [s for s in sales if lo <= s["price"] <= hi]
    return kept or sales


def estimate(c, half_life, agg, use_miles, ref, boost_n, boost_w, use_cs, fence=None,
             small_n_mean=0, clamp=False):
    make, model, year = car_inputs(c)
    sales = fence_filter(c["listed_sales"], fence)
    if len(sales) <= small_n_mean:
        return sum(s["price"] for s in sales) / len(sales)
    ref_date = (date.fromisoformat(c["as_of"]) if c["as_of"] else FETCHED) if ref == "asof" \
        else date.fromisoformat(max(s["date"] for s in sales))
    typical = c["avg_miles"]
    approx_val = sorted(s["price"] for s in sales)[len(sales) // 2]
    cs = collectibility(make, model, year, approx_val, c.get("msrp"), 2026).score if use_cs else None
    age = 2026 - year if use_cs else None
    pts = []
    order = sorted(sales, key=lambda s: s["date"], reverse=True)
    for i, s in enumerate(order):
        v = s["price"]
        if use_miles and s["miles"] and typical:
            v = v / (mileage_adjust(1_000_000, s["miles"], typical, cs, age) / 1_000_000)
        days = (ref_date - date.fromisoformat(s["date"])).days
        w = 0.5 ** (days / (half_life * 365.25)) if half_life else 1.0
        if i < boost_n:
            w *= boost_w
        pts.append((v, w))
    if agg == "mean":
        est = sum(v * w for v, w in pts) / sum(w for _, w in pts)
    else:
        pts.sort()
        half, acc, est = sum(w for _, w in pts) / 2, 0.0, pts[-1][0]
        for v, w in pts:
            acc += w
            if acc >= half:
                est = v
                break
    if clamp and len(pts) >= 4:
        vs = [v for v, _ in pts]
        est = min(_pct(vs, 0.75), max(_pct(vs, 0.25), est))
    return est


def main(path):
    cars = [c for c in json.load(open(path)) if c["fully_listed"] and c["market_value"]
            and c["sales_count"] >= 2]
    grid = itertools.product([0.25, 0.4, 0.5, 0.75, 1, 1.5], ["mean", "median"], [True, False],
                             ["asof"], [0, 1, 3], [1, 2, 4], [True, False],
                             [None, "iqr1.0", "iqr1.5", "ratio1.5", "ratio2.0"], [0, 2], [False, True])
    results = []
    for hl, agg, mi, ref, bn, bw, cs, fence, small, clamp in grid:
        if bn == 0 and bw != 1:
            continue
        errs = [abs(estimate(c, hl, agg, mi, ref, bn, bw, cs, fence, small, clamp)
                    / c["market_value"] - 1) for c in cars]
        results.append((sum(errs) / len(errs), sorted(errs)[len(errs) // 2],
                        dict(half_life=hl, agg=agg, miles=mi, ref=ref, boost_n=bn, boost_w=bw,
                             collect=cs, fence=fence, small_n_mean=small, clamp=clamp)))
    results.sort(key=lambda r: r[0])
    print(f"{len(cars)} fully listed cars with a market value and 2+ sales\n")
    for mape, med, p in results[:10]:
        print(f"MAPE {mape:6.1%}  median err {med:6.1%}  {p}")
    best = results[0][2]
    print("\nPer-car with best params:")
    for c in cars:
        e = estimate(c, *best.values())
        print(f"  {c['name'][:42]:42} n={c['sales_count']:2} published={c['market_value']:>9,} "
              f"ours={e:>11,.0f} err={e / c['market_value'] - 1:+6.1%}")
    return results


if __name__ == "__main__":
    main(sys.argv[1])
