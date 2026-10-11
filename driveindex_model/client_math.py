"""Faithful Python port of the valuation math shipped in driveindex.com's client bundle.

Source: https://driveindex.com/_next/static/chunks/app/(app)/dashboard/page-fed0112594c462d4.js
(captured 2026-10-11 with REA `inspect-web-page --include-script-sources`, exported with
`export-web-scripts`, prettified). Line numbers in comments refer to the prettified bundle.

Every constant below is copied from the bundle; nothing is tuned or guessed. Inputs such as
`annual_return`, `recent_return`, `confidence` and `signal` are produced server-side by
DriveIndex and arrive via /api/cars/<id>; see estimators.py for reconstructions of those.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

SIGNALS = ("appreciating", "stable", "depreciating", "approaching", "bottomed", "insufficient")
SIGNAL_LABELS = {
    "appreciating": "Appreciating",
    "depreciating": "Depreciating",
    "stable": "Stable",
    "approaching": "Near Bottom",
    "bottomed": "Bottomed Out",
    "insufficient": "Insufficient Data",
}


def _js_round(x: float) -> int:
    """JavaScript Math.round (half rounds toward +inf), unlike Python's banker's rounding."""
    return math.floor(x + 0.5)


def _r2(x: float) -> float:
    return _js_round(100 * x) / 100


# ---------------------------------------------------------------------------
# 1. Collectibility score (bundle lines 23-319)
# ---------------------------------------------------------------------------

CURATED_SCORES = {
    "918 SPYDER": 10, "LAFERRARI": 10, "P1": 10, "F40": 10, "F50": 10, "ENZO": 10,
    "CARRERA GT": 10, "SLR MCLAREN": 10, "CLK GTR": 10, "VEYRON": 10, "CHIRON": 10,
    "ZONDA": 10, "HUAYRA": 10, "CENTENARIO": 10, "VENENO": 10, "REVENTON": 10, "MIURA": 10,
    "COUNTACH": 10, "GT40": 10, "AMG ONE": 10, "SENNA": 10, "SPEEDTAIL": 10, "VALKYRIE": 10,
    "812 COMPETIZIONE": 10, "288 GTO": 10, "250 GTO": 10, "FORD GT": 10, "2000GT": 10,
    "959": 10, "SLS AMG": 9, "SLS AMG BLACK SERIES": 10, "SLS AMG GT FINAL EDITION": 9,
    "GT2 RS": 9, "GT3 RS": 9, "GT4 RS": 9, "CAYMAN GT4 RS": 9, "488 PISTA": 9,
    "458 SPECIALE": 9, "430 SCUDERIA": 9, "CHALLENGE STRADALE": 9, "SF90 STRADALE": 9,
    "SF90 SPIDER": 9, "F8 TRIBUTO": 9, "F8 SPIDER": 9, "HURACAN STO": 9,
    "HURACAN PERFORMANTE": 9, "AVENTADOR SVJ": 9, "765LT": 9, "600LT": 9, "720S": 9,
    "AMG GT BLACK SERIES": 9, "AMG GT R": 9, "GT BLACK SERIES": 9, "GT R": 9,
    "CORVETTE ZR1": 9, "CORVETTE Z06": 9, "CHALLENGER SRT DEMON": 9,
    "CHALLENGER SRT DEMON 170": 9, "VIPER ACR": 9, "GT-R NISMO": 9, "M3 CSL": 9, "M4 CSL": 9,
    "MUSTANG SHELBY GT500": 9, "MUSTANG SHELBY GT350": 9, "MUSTANG SHELBY GT350R": 9,
    "HEMI CUDA": 9, "CHARGER DAYTONA": 9, "12CILINDRI": 9, "12CILINDRI SPIDER": 9,
    "911 S/T": 10, "REVUELTO": 10, "BATUR": 10, "GT3": 8, "GT3 TOURING": 8, "TURBO S": 8,
    "CAYMAN GT4": 8, "SPORT CLASSIC": 8, "SPEEDSTER": 8, "812 SUPERFAST": 8, "812 GTS": 8,
    "F12BERLINETTA": 8, "488 GTB": 8, "488 SPIDER": 8, "296 GTB": 8, "296 GTS": 8,
    "PUROSANGUE": 8, "DB12": 7, "SPECTRE": 8, "URUS PERFORMANTE": 8, "750S": 8,
    "HURACAN TECNICA": 8, "AVENTADOR": 8, "AVENTADOR S": 8, "570S": 8, "ARTURA": 8,
    "DBS SUPERLEGGERA": 8, "DB11": 8, "M5 CS": 8, "M4 CS": 8, "M3 COMPETITION": 8,
    "M4 GTS": 8, "VIPER": 8, "CAMARO ZL1": 8, "CAMARO Z28": 8, "NSX": 8, "LFA": 8, "RX-7": 8,
}
ULTRA_RARE = [
    "ENZO", "F40", "F50", "LAFERRARI", "CLK GTR", "SLR MCLAREN", "CARRERA GT", "918 SPYDER",
    "P1", "SENNA", "SPEEDTAIL", "AMG ONE", "VEYRON", "CHIRON", "ZONDA", "HUAYRA", "CENTENARIO",
    "VENENO", "REVENTON", "MIURA", "COUNTACH", "GT40", "FORD GT", "VALKYRIE",
    "812 COMPETIZIONE", "288 GTO", "250 GTO", "959", "2000GT", "SLS AMG",
]
TRACK_FOCUSED = [
    "GT2 RS", "GT3 RS", "GT4 RS", "BLACK SERIES", "CSL", "Z06", "ZR1", "GT350R", "GT500",
    "SPORT CLASSIC", "PERFORMANTE", "SVJ", "STO", "SCUDERIA", "PISTA", "SPECIALE",
    "CHALLENGE STRADALE", "600LT", "765LT", "GT3 TOURING", "SPEEDSTER", "GT2", "MURCIELAGO",
    "AVENTADOR", "DIABLO", "AMG GT R", "GT R", "DEMON", "ACR", "NISMO", "HEMI CUDA",
]
PERFORMANCE = [
    "GT3", "GT4", "GTS", "TURBO S", "M3", "M4", "M5", "M2", "C63", "E63", "AMG GT", "RS3",
    "RS4", "RS5", "RS6", "RS7", "TYPE R", "STI", "NISMO", "NSX", "SUPRA", "SKYLINE", "RX-7",
    "LFA", "VANTAGE", "DB11", "DBS", "CONTINENTAL GT", "WRAITH", "720S", "570S", "488", "F8",
    "SF90", "812",
]
MASS_PRODUCTION = [
    "CAYENNE", "MACAN", "PANAMERA", "URUS", "LEVANTE", "GHIBLI", "X3", "X5", "Q5", "Q7",
    "GLE", "GLC", "RANGE ROVER SPORT", "F-PACE", "FLYING SPUR", "CULLINAN", "BENTAYGA",
]
STRONG_BRANDS = ["Ferrari", "Porsche", "Lamborghini", "Bugatti", "Pagani", "Koenigsegg",
                 "McLaren", "Aston Martin"]
WEAK_BRANDS = ["Maserati", "Jaguar", "Land Rover"]


@dataclass
class Collectibility:
    score: int
    reasons: list[str] = field(default_factory=list)
    curated: bool = False


def collectibility(make: str, model: str, year: int, value: float,
                   msrp: float | None = None, now_year: int | None = None) -> Collectibility:
    """Rule-based 1-10 collectibility score (bundle fn `m`, lines 264-319)."""
    o, reasons = 5, []
    s = model.upper()
    age = (now_year if now_year is not None else date.today().year) - year
    if any(k in s for k in ULTRA_RARE):
        o += 4; reasons.append("Ultra-rare limited production")
    elif any(k in s for k in TRACK_FOCUSED):
        o += 3; reasons.append("Very limited / track-focused")
    elif any(k in s for k in PERFORMANCE):
        o += 2; reasons.append("Desirable performance model")
    elif any(k in s for k in MASS_PRODUCTION):
        o -= 2; reasons.append("Mass-production model")
    if "MANUAL" in s or "6-SPEED" in s or "6 SPEED" in s:
        o += 1; reasons.append("Manual transmission")
    if value > 500_000:
        o += 2; reasons.append("High-value segment (>$500K)")
    elif value > 200_000:
        o += 1; reasons.append("Premium segment ($200K+)")
    elif value < 30_000:
        o -= 1; reasons.append("Entry-level pricing")
    if msrp and msrp > 0:
        ratio = value / msrp
        if ratio > 1.5:
            o += 2; reasons.append("Trading well above MSRP")
        elif ratio > 1.1:
            o += 1; reasons.append("Trading above MSRP")
    if 20 <= age <= 35:
        o += 1; reasons.append("Classic age — peak collectibility")
    elif age >= 40:
        o += 1; reasons.append("Vintage — established collector market")
    if make in STRONG_BRANDS:
        o += 1; reasons.append(f"{make} — strong collector brand")
    elif make in WEAK_BRANDS:
        o -= 1; reasons.append(f"{make} — historically depreciates")
    # Curated list overrides the computed score; the longest matching key wins.
    hits = sorted((k for k in CURATED_SCORES if k in s), key=len, reverse=True)
    if hits:
        score = CURATED_SCORES[hits[0]]
        if not reasons:
            reasons.append(f"Recognized benchmark collectible — verified {score}/10 rating")
        return Collectibility(score, reasons, True)
    return Collectibility(max(1, min(10, o)), reasons)


# ---------------------------------------------------------------------------
# 2. Projection engine: forecast1y/3y/5y + bear/base/bull (bundle lines 320-566)
# ---------------------------------------------------------------------------

def blend_decline_rate(rate: float, recent_return: float | None, signal: str) -> float:
    """Blend the long-run annual rate with the recent (12-mo) return (bundle fn `x`)."""
    if recent_return is None:
        return min(0.0, rate)
    k = 0.25 if signal == "approaching" else 0.5
    return max(2 * rate, min(k * rate, 0.3 * recent_return + 0.7 * rate))


@dataclass
class RateModel:
    blended_rate: float
    dampening: float
    collectibility_score: int
    age: int
    collectibility: Collectibility
    floor: int
    data_trend: float
    age_factor: float
    msrp_factor: float
    momentum_factor: float


def rate_model(value, annual_return, confidence, sample_size, signal, year, make, model,
               msrp=None, now_year=None) -> RateModel:
    """Five-factor blended annual growth rate + yearly dampening (lines 355-447)."""
    g = annual_return or 0.0
    col = collectibility(make, model, year, value, msrp, now_year)
    h = col.score
    u = (h - 5) * 0.01  # collectibility factor

    f = 0.0  # MSRP factor
    if msrp and msrp > 0:
        t = value / msrp
        f = 0.03 if t > 2 else 0.02 if t > 1.2 else -0.01 if t > 0.8 else -0.02 if t > 0.5 else 0.01

    age = (now_year if now_year is not None else date.today().year) - year
    x = (-0.10 if age <= 2 else -0.06 if age <= 5 else -0.02 if age <= 10
         else 0.01 if age <= 20 else 0.03 if age <= 35 else 0.04)
    if age > 6:
        if h >= 8: x = max(x, 0.02)
        elif h >= 6: x = max(x, -0.02)
    else:
        if h >= 8: x = max(x, -0.03)
        elif h >= 6: x = max(x, -0.04)

    v = {"appreciating": 0.02, "bottomed": 0.03, "approaching": 0.01,
         "depreciating": -0.02}.get(signal, 0.0)  # momentum factor
    b = min(0.0, u) if age <= 5 else u

    if signal in ("depreciating", "appreciating"):
        w = (0.65, 0.13, 0.12, 0.06, 0.04)
    elif signal == "approaching":
        w = (0.55, 0.15, 0.13, 0.10, 0.07)
    elif sample_size >= 25 and confidence > 0.5:
        w = (0.50, 0.20, 0.10, 0.10, 0.10)
    elif sample_size >= 10:
        w = (0.35, 0.25, 0.15, 0.15, 0.10)
    else:
        w = (0.20, 0.30, 0.25, 0.15, 0.10)
    c = w[0] * g + w[1] * b + w[2] * x + w[3] * f + w[4] * v
    lo = -0.06 if h >= 8 else -0.10 if h >= 6 else -0.15
    hi = 0.14 if h >= 9 else 0.12 if h >= 7 else 0.10 if h >= 5 else 0.08
    c = max(lo, min(hi, c))
    if signal in ("depreciating", "approaching") and g <= -0.03:
        c = min(c, (0.34 if signal == "approaching" else 0.65 if age <= 5 else 0.5) * g)

    damp = 0.94 if h >= 9 else 0.90 if h >= 7 else 0.85 if h >= 5 else 0.82
    if c < -0.05:
        a = abs(c)
        damp = 0.62 if a >= 0.12 else 0.70 if a >= 0.08 else 0.78

    return RateModel(c, damp, h, age, col, _js_round(0.4 * value), g, x, f, v)


@dataclass
class ValuePath:
    vals: list[float]
    raw_vals: list[float]
    bottom_year: float
    bottom_value: int
    falling: bool


def value_path(value: float, m: RateModel, signal: str, recent_return: float | None,
               horizon_years: int = 15, backtest_raw_move: bool = False) -> ValuePath:
    """Year-by-year value path (lines 449-537). Falling cars step quarterly toward a bottom."""
    a, damp, floor = m.blended_rate, m.dampening, m.floor
    falling = (signal in ("depreciating", "approaching")
               or (signal not in ("appreciating", "bottomed", "stable")
                   and a < 0 and blend_decline_rate(a, recent_return, signal) < 0))
    vals = [float(value)] + [0.0] * horizon_years
    bottom_year, bottom_val = 0.0, float(value)

    if falling:
        o = blend_decline_rate(a, recent_return, signal)
        if o >= 0:
            o = min(a, -0.01)
        young = m.age <= 5
        q_damp = (max(0.45, min(0.76, 0.76 - 2.2 * (min(0.16, max(0.02, abs(o))) - 0.02)))
                  * (1 if young else 0.65)) ** 0.25
        o *= 1 if young else 0.35
        hq = (1 + o) ** 0.25 - 1           # quarterly decline rate
        recov = 1.015 ** 0.25 - 1          # 1.5%/yr recovery after the bottom
        stop = max(0.006, 0.35 * abs(o))   # annualised decline below this => bottom reached
        y, bottomed = float(value), False
        for t in range(1, 4 * horizon_years + 1):
            if not bottomed and t >= 2 and abs((1 + hq) ** 4 - 1) < stop:
                bottomed, bottom_year, bottom_val = True, (t - 1) / 4, y
            if bottomed:
                cap = bottom_val + 0.6 * (value - bottom_val)  # recover at most 60% of the drop
                y *= 1 + recov
                if y > cap: y = cap
            else:
                y *= 1 + hq
                if y < floor: y = floor
                hq *= q_damp
            if t % 4 == 0:
                vals[t // 4] = y
        if not bottomed:
            bottom_year, bottom_val = horizon_years, y
    else:
        t = float(value)
        if signal in ("appreciating", "bottomed"):
            n = max(0.026 if signal == "bottomed" else 0.012, a)
        else:
            n = a if abs(a) >= 0.018 else (-0.018 if a < 0 else 0.018)
        for e in range(1, horizon_years + 1):
            t *= 1 + n
            if t < floor: t = floor
            vals[e] = t
            n = max(0.012, n * damp) if n >= 0 else min(-0.012, n * damp)

    # Appreciating cars: only part of the modelled gain is shown (conservatism shrink).
    if backtest_raw_move or signal == "bottomed" or signal != "appreciating":
        shrink = 1.0
    elif m.collectibility_score >= 8:
        shrink = 0.3
    else:
        shrink = 0.25 - 0.2 * max(0.0, min(1.0, (m.data_trend - 0.08) / 0.06))
    raw = list(vals)
    if shrink < 1:
        for i in range(1, horizon_years + 1):
            vals[i] = value + shrink * (vals[i] - value)
    bv = _js_round(bottom_val) if falling else _js_round(min(vals))
    return ValuePath(vals, raw, max(bottom_year, 0.25) if falling and bv < value else 0.0,
                     bv, falling)


@dataclass
class Projection:
    forecast1y: int
    forecast3y: int
    forecast5y: int
    bear3y: int
    bull3y: int
    bear5y: int
    bull5y: int
    momentum3y: int
    momentum5y: int
    confidence_3y_pct: int
    confidence_5y_pct: int
    bottom_value: int
    bottom_year: float
    rate: RateModel


def project(value, annual_return, confidence, sample_size, signal, year, make, model,
            msrp=None, recent_return=None, now_year=None) -> Projection | None:
    """Full projection (bundle fn `v`, lines 331-566)."""
    if not value or value <= 0:
        return None
    m = rate_model(value, annual_return, confidence, sample_size, signal, year, make, model,
                   msrp, now_year)
    p = value_path(value, m, signal, recent_return)
    b3, b5 = _js_round(p.vals[3]), _js_round(p.vals[5])
    unc = max(0.15, 1 - (confidence or 0.3))  # band width grows as confidence falls
    return Projection(
        forecast1y=_js_round(p.vals[1]), forecast3y=b3, forecast5y=b5,
        bear3y=max(p.bottom_value, _js_round(b3 * (0.92 - 0.15 * unc))),
        bull3y=_js_round(b3 * (1.10 + 0.18 * unc)),
        bear5y=max(p.bottom_value, _js_round(b5 * (0.88 - 0.22 * unc))),
        bull5y=_js_round(b5 * (1.15 + 0.28 * unc)),
        momentum3y=max(b3, _js_round(p.raw_vals[3])),
        momentum5y=max(b5, _js_round(p.raw_vals[5])),
        confidence_3y_pct=_js_round(100 * (confidence or 0)),
        confidence_5y_pct=_js_round(80 * (confidence or 0)),
        bottom_value=p.bottom_value, bottom_year=p.bottom_year, rate=m,
    )


def cagr(future: float, now: float, years: float = 3) -> float:
    """Annualised rate shown next to projections (bundle `tq`)."""
    return (future / now) ** (1 / years) - 1 if future > 0 and now > 0 else 0.0


# ---------------------------------------------------------------------------
# 3. Data-strength badge: "Strong / Moderate / Low data" (lines 567-603)
# ---------------------------------------------------------------------------

def data_strength(n_sales: float, fit_quality: float, dispersion: float) -> tuple[str, float]:
    """Weighted 0-1 score: 40% sample size, 35% fit quality, 25% price dispersion.

    The bundle names the inputs only positionally. From the breakpoints, `fit_quality`
    saturates at 0.45 (consistent with an R^2 / confidence) and `dispersion` is best at
    <=0.18 (consistent with a coefficient of variation). Those two labels are inferences.
    """
    n = n_sales if math.isfinite(n_sales) else 0
    i = fit_quality if math.isfinite(fit_quality) else 0
    a = dispersion if math.isfinite(dispersion) else 0
    size = 1 if n >= 20 else 0.8 if n >= 12 else 0.6 if n >= 8 else 0.4 if n >= 5 else 0.2 if n >= 3 else 0
    disp = (0.5 if a <= 0 else 1 if a <= 0.18 else 0.75 if a <= 0.28 else 0.5 if a <= 0.4
            else 0.25 if a <= 0.55 else 0)
    o = 0.4 * size + 0.35 * max(0.0, min(1.0, (i - 0.1) / 0.35)) + 0.25 * disp
    level = "high" if o >= 0.62 else "moderate" if o >= 0.36 else "low"
    if level == "high" and (n < 12 or a > 0.4):
        level = "moderate"
    if n < 4:
        level = "low"
    return level, _r2(o)


# ---------------------------------------------------------------------------
# 4. Mileage adjustment (fn `k`, lines 621-676) and dealer premium (fn `S`, lines 604-620)
# ---------------------------------------------------------------------------

def mileage_adjust(value: float, miles: float | None, avg_miles: float | None,
                   collect_score: float | None = None, age: float | None = None) -> int:
    """Re-price a model-average-mileage value to a specific odometer reading.

    Piecewise-linear premium for below-average miles (scaled by collectibility and age,
    extra bump for <=500 / <=1,000 mi) and a gentler discount for above-average miles.
    """
    if not value or value <= 0:
        return 0
    if not miles or not avg_miles or avg_miles <= 0:
        return value
    o = (miles - avg_miles) / max(avg_miles, 5000)
    l = abs(o)
    s = 1.0
    if collect_score is not None:
        s = 1.5 if collect_score >= 9 else 1.2 if collect_score >= 7 else 1.0 if collect_score >= 5 else 0.7
    d = 1.0
    if age is not None and o < 0:
        d = 1.5 if age >= 30 else 1.3 if age >= 20 else 1.1 if age >= 10 else 1.0
    if o < 0:
        if l < 0.15:
            a = 0.05 * l * s
        elif l < 0.4:
            a = 0.0075 + (l - 0.15) * 0.15 * s
        elif l < 0.7:
            a = (0.045 + (l - 0.4) * 0.3 * s) * d
        else:
            a = (0.135 + (l - 0.7) * 0.6 * s) * d
            if miles <= 500: a *= 1.25
            elif miles <= 1000: a *= 1.1
    else:
        e = 0.8 if s >= 1.5 else 0.9 if s >= 1.2 else 1.0
        if l < 0.25:
            a = -(0.02 * l * e)
        elif l < 0.75:
            a = -(0.005 + (l - 0.25) * 0.05 * e)
        elif l < 2:
            a = -(0.03 + (l - 0.75) * 0.08)
        else:
            a = -(0.13 + (l - 2) * 0.1)
    cs = collect_score
    lo = -(0.3 if cs is not None and cs >= 9 else 0.25 if cs is not None and cs >= 7 else 0.3)
    hi = (0.45 if cs is not None and cs >= 9 else 0.3 if cs is not None and cs >= 7
          else 0.2 if cs is not None and cs >= 5 else 0.15)
    a = max(lo, min(hi, a))
    return _js_round(value * (1 + a))


DEALER_PREMIUM_CURVE = [(25_000, 0.10), (75_000, 0.0), (150_000, 0.075), (350_000, 0.045),
                        (500_000, 0.09)]


def dealer_premium(price: float) -> float:
    """Retail-over-auction markup added to the fair ask, linear between knots."""
    pts = DEALER_PREMIUM_CURVE
    if price <= pts[0][0]:
        return pts[0][1]
    if price >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if price <= x1:
            return y0 + (price - x0) / (x1 - x0) * (y1 - y0)
    return pts[-1][1]


# ---------------------------------------------------------------------------
# 5. Listing Analyzer: fair ask, verdict, deal score (fn `cT` line 15532, `cv` line 14541)
# ---------------------------------------------------------------------------

@dataclass
class ListingVerdict:
    signal: str          # great | below | fair | above | overpriced
    diff: float          # (ask - fair_ask) / fair_ask
    fair_ask: int
    deal_score: int      # 5..98


VERDICT_LABELS = {"great": "Great deal", "below": "Below market", "fair": "Fair",
                  "above": "Above market", "overpriced": "Overpriced"}


def analyze_listing(ask: float, market_value: float, miles: float | None = None,
                    avg_miles: float | None = None, collect_score: float | None = None,
                    age: float | None = None, value_is_listing_based: bool = False) -> ListingVerdict:
    adj = market_value
    if miles and avg_miles and avg_miles > 0 and market_value > 0:
        adj = mileage_adjust(market_value, miles, avg_miles, collect_score, age)
    if not adj or adj <= 0:
        return ListingVerdict("fair", 0.0, market_value, 55)
    prem = 0.0 if value_is_listing_based else dealer_premium(adj)
    fair = _js_round(adj * (1 + prem))
    c = (ask - fair) / fair
    sig = ("great" if c <= -0.12 else "below" if c <= -0.04 else "fair" if c <= 0.06
           else "above" if c <= 0.15 else "overpriced")
    return ListingVerdict(sig, c, fair, max(5, min(98, _js_round(55 - 250 * c))))


def sold_result_label(sold_price: float, expected: float) -> str:
    """Auction-result badge: <-4% Below Market, >+6% Above Market (line ~20175)."""
    pct = (sold_price - expected) / expected * 100 if expected > 0 else 0
    return "Below Market" if pct < -4 else "Above Market" if pct > 6 else "Market Price"


# ---------------------------------------------------------------------------
# 6. Sellability / months of supply (fn `cj`, lines ~14690-14830)
# ---------------------------------------------------------------------------

def sellability(sales_last_24m: int, active_listings: int) -> tuple[str, float | None]:
    if sales_last_24m == 0 and active_listings == 0:
        return "none", None
    if sales_last_24m < 4:
        return "thin", None
    months = active_listings / max(0.5, sales_last_24m / 2) * 12
    if active_listings <= 1:
        return "tight", months
    if months < 6:
        return "sellers", months
    if months <= 18:
        return "balanced", months
    return "buyers", months


# ---------------------------------------------------------------------------
# 7. Desirability / liquidity / resale scores (fn `cb`, lines ~14630-14690)
# ---------------------------------------------------------------------------

def spec_scores(signal, miles, msrp, sales_count, recent_sales_count, confidence,
                annual_return, liquidity_tier=None) -> dict:
    g = p = h = 50
    if signal == "appreciating": g += 20; h += 15
    if signal == "bottomed": g += 10; h += 20
    if signal == "depreciating": g -= 10; h -= 15
    if miles and miles < 10_000: g += 15
    if miles and miles > 50_000: g -= 10
    if msrp and msrp > 200_000: g += 10
    p = min(95, 25 + min(20, sales_count) + 8 * (recent_sales_count or 0)
            + _js_round(25 * (confidence or 0)))
    if signal == "appreciating": p += 8
    h += _js_round(100 * (annual_return or 0))
    tiers = {"high": ("High", 85), "moderate": ("Moderate", 58), "low": ("Low", 30)}
    lab, s = tiers.get(liquidity_tier) or (
        "High" if p > 70 else "Moderate" if p > 45 else "Low", max(10, min(99, p)))
    return {"desirability": max(10, min(99, g)), "liquidity": lab, "liquidity_score": s,
            "resale": "Strong" if h > 65 else "Moderate" if h > 40 else "Weak",
            "resale_score": max(10, min(99, h))}


def best_buy_rank(signal, annual_return, recent_return, sales_count, confidence) -> float:
    """Ranking score for the budget "best buys" finder (fn `lP`, line ~12524)."""
    clamp = lambda z: max(-0.15, min(0.25, z or 0))
    base = {"appreciating": 2.5, "bottomed": 2, "stable": 1, "approaching": 0.4}.get(signal, 0)
    return (base + 10 * clamp(annual_return) + 6 * clamp(recent_return)
            + min(1.5, (sales_count or 0) / 40) + 1.5 * (confidence or 0))


# ---------------------------------------------------------------------------
# 8. Seasonality read-out and chart smoothing
# ---------------------------------------------------------------------------

def seasonal_read(monthly_indices: list[float], best_months: list[int], worst_months: list[int],
                  strength_pct: float) -> dict:
    """Best/worst month text. Indices are server-side (1.0 = average month).
    Requires 20+ sales across 4+ months spanning 1.5+ years (stated in the UI)."""
    return {
        "buy_discount_pct": max(0, _js_round((1 - monthly_indices[best_months[0]]) * 100)),
        "sell_premium_pct": max(0, _js_round((monthly_indices[worst_months[0]] - 1) * 100)),
        "strength": ("strong" if strength_pct >= 15 else "moderate" if strength_pct >= 7
                     else "mild"),
    }


def gaussian_smooth(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Price-history chart line: Nadaraya-Watson Gaussian kernel over sale dates (ms).
    Bandwidth = span/8 clamped to [20 days, 90 days]."""
    if not points:
        return []
    span = max(p[0] for p in points) - min(p[0] for p in points)
    bw = min(max(span / 8, 1728e6), 7776e6)
    out = []
    for t, price in points:
        ws = [(math.exp(-0.5 * ((t - d) / bw) ** 2), p) for d, p in points]
        tot = sum(w for w, _ in ws)
        out.append((t, sum(w * p for w, p in ws) / tot if tot > 0 else price))
    return out
