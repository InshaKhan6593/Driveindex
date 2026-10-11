# Validation against live driveindex.com pages

Date: 2026-10-11. Data: 104 public car-year pages (44 random + 60 cars from the labelled
appreciation/depreciation lists, 101 unique cars), parsed by `scripts/parse_car_page.py`. Stored in
`tests/data/`, checked by `tests/test_fully_listed_cars.py`.

A page is **fully listed** when it shows every sale behind its numbers (sales shown = published
"verified auction sales"). That happens for cars with 15 sales or fewer, so it's the low-sales
end of the catalogue. **54 cars** qualified, from 1 to 15 sales each.

## Scope

* Only public `/cars/...` pages, fetched 1.5 s apart.
* `/api/*` and `/dashboard` were **not** called. The session's permission check blocked direct
  API requests (robots.txt disallows them). Ownership of the site can't be verified from here,
  so no workaround was attempted. To test the API too, allow those requests in the Claude Code
  permission settings, or run the scripts yourself with your own API access.

## Results

| Check | Result |
|---|---|
| Median sale | **54 / 54 exact** (rounded to whole dollars, half up) |
| Typical range (P25–P75) | **32 / 32 exact** with `sorted[Math.round((n−1)·q)]`. Linear interpolation matches only 4/10 |
| Typical range hidden below 8 sales | 22 / 22 |
| 1-sale cars: value = that sale | 2 / 2 |
| Market value, calibration set (18 cars, 2–15 sales) | **MAPE 3.2%, median error 1.7%**, 12/18 within 3% |
| Market value, holdout (35 labelled cars, unseen) | MAPE 10.2%, median error 7.3%, 22/35 within 10% |
| Value Signal label (35 labelled cars) | **26 / 35 (74%)**: depreciating 16/18, appreciating 10/16, bottomed 0/1 |
| Long-run "since YEAR" = year of first sale | 32 / 35 |
| Long-run %/yr magnitude | not reproducible from sales alone (median error about 7 pts, see below) |

## What the data showed

**Market value**, fitted with `scripts/calibrate_market_value.py`:
1. Drop prices outside 1.5 × IQR (only with 4+ sales). Example: the 2010 Cayman's newest
   $44,500 sale is 1.65 × its median, and the published value ignores it.
2. Normalise each sale to the published average mileage by inverting the client mileage
   curve.
3. Recency-weighted mean with a short half-life of about **0.3 years**. Values follow the
   newest sales closely: the 2020 Macan GTS is $43,997 against a $53,000 median.
4. If the newest sale is 3+ years old, use the plain median. The 1998 GT1 is exactly the
   mean of its two sales from 2012 and 2017.

Per-car errors on the calibration set: Turbo S Coupe −0.1%, Targa 4S (991.2) +0.5%, GT4
Clubsport −0.4%, Macan GTS +0.6%, Taycan −1.9%. The worst are the 2020 Cayenne (+11.5%) and
2013 Panamera (+11.2%), both high-mileage cars with very-low-mileage recent sales. Your
server likely uses a stronger mileage curve than the client one.

The holdout errors are larger because the labelled cars are the market's extreme movers
(±10–30 %/yr), where a small difference in recency weighting moves the value a lot.

**Low-sales behaviour:**
* With 1 sale, the value equals that sale. A "No sale since …" warning appears when the newest
  sale is old, and the value then disappears from JSON-LD and only appears in the page text.
* Below 8 sales the page shows the full "Price Range" instead of "Typical Range".
* Price history by year only shows years with 3+ sales.
* **Signals are assigned from as few as 2 sales.** The 1966 Nova Sport Coupe (2 sales) is listed
  as appreciating. None of the 101 cars showed "Limited Data".

**Long-run %/yr:** the API exposes `valueFirst`/`valueFirstAt`. The rate compares today's value
with a *stored* historical value from DriveIndex's database. Recomputing that historical value
from today's sales list doesn't reproduce it (median error about 7 pts for every variant
tried: CAGR from the first sale, OLS slope, fitted-line CAGR, estimator at the k-th sale).
Only the "since" year, the year of the first sale, is reproducible.

**Classifier misses:** 5 appreciating cars came out "stable" (thresholds too wide for fast
risers with few sales), and the one bottomed car came out "stable". Tuning the thresholds on
this set didn't get past 26/35. The real rule needs more than year-median slopes.

## REA test run

All REA (`rea-agents@6.4.0`) website tools were exercised on
`/cars/porsche/macan-gts/2020`, a 5-sale car:

| Command | Result |
|---|---|
| `list-browser-targets` | target found, Chrome 141 |
| `capture-web-screenshot` | 1366×708 PNG: `docs/rea/macan_gts_2020_screenshot.png` |
| `observe-web-session` | 4 lifecycle events (commit → load) |
| `inspect-web-page` + JSON shapes + scripts + console | 35 scripts. 0 network requests, because REA attaches passively *after* load (`prior_activity_available: false`) |
| `export-web-scripts` | 35 scripts written and verified |
| `analyze-javascript-application` | 35 files parsed, 0 failures, 223 modules, 729 findings, 441k AST nodes |
| `analyze-web-bundle` (earlier run) | Next.js/React fingerprints, 70+ `/api/*` endpoint candidates |

REA's limit for this job: it observes and parses what the browser already has. It can't see
server code, so the scrapers and the classifier stay out of reach. To capture network
traffic, start the observation window before navigating (`observe-web-session`), or record
a HAR and analyse it with REA's capture tools.
