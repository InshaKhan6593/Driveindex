# DriveIndex.com: reverse-engineering report

Target: https://driveindex.com ("Car Market Intelligence & Value Tracking", Radin INC, Los Angeles)
Captured: 2026-10-11
Tooling: [REA, Reverse Engineer Anything](https://github.com/morluto/rea) `rea-agents@6.4.0`
(website observation over CDP, bundle analysis, script export), plus headless Chromium 141.

## TL;DR

* The site is Next.js (App Router, React Server Components) on Vercel. Public pages are
  server-rendered SEO pages. The paid product is a single client-side dashboard
  (`/dashboard`, `app/(app)/dashboard/page-*.js`, about 1.1 MB minified) that talks to a JSON API under `/api/*`.
* **The forecasting and pricing math runs in the browser.** The projection engine (1/3/5-year
  forecasts with bear/base/bull bands), the collectibility score, the mileage-adjustment curve,
  the dealer-premium curve, the Listing Analyzer verdicts, the deal score, the "data strength"
  badge, sellability (months of supply), desirability/liquidity/resale scores and the
  chart smoothing are all in that chunk. They are ported line-for-line in
  [`driveindex_model/client_math.py`](../driveindex_model/client_math.py), and the port
  **matches the original JS on 2,400 randomized test cases** (`tests/test_parity.py`).
* **Server-side only:** the scraped sales database (318k results / 258k verified sales / 25
  sources), outlier filtering, the market-value estimator, and the Value Signal inputs
  (`annualReturn`, `recentReturn`, `confidence`, `signal`), plus seasonality indices. These
  arrive precomputed from `/api/cars/<id>`. The public rules are reproduced exactly in
  [`estimators.py`](../driveindex_model/estimators.py) Part A. The hidden estimator and signal
  are reconstructed in Part B. Using only the 15 publicly listed sales of a 2020 GT350R, the
  reconstruction gives $111,402 against the site's $114,593.

## 1. How it was captured (REA)

```
chromium --headless=new --remote-debugging-port=9222 https://driveindex.com/cars/ford/mustang-shelby-gt350r/2020
rea list-browser-targets  http://127.0.0.1:9222 --json
rea inspect-web-page      http://127.0.0.1:9222 <target> --include-json-body-shapes --include-script-sources --json
rea analyze-web-bundle    http://127.0.0.1:9222 <target> --json
rea export-web-scripts    inspect.json ./scripts --json
```

Full script: [`scripts/rea_capture.sh`](../scripts/rea_capture.sh). REA reported 38 scripts,
Next.js + React fingerprints, 4 source-map declarations and the endpoint list below. The math
was then read from the prettified dashboard chunk (line numbers below refer to it).

Scope note: `robots.txt` disallows `/api/`, `/admin/` and `/dashboard`. This work did not
crawl those paths or call the API. Only public pages and the JS files they load were read.

## 2. Architecture

| Layer | Finding |
|---|---|
| Framework | Next.js App Router, RSC payloads (`self.__next_f`), route groups `(marketing)` and `(app)` |
| Hosting | Vercel (`?dpl=dpl_…` deployment IDs on every asset) |
| Data model | Cars keyed by cuid (`cmnds2xv7000ekeppbstvp2c0`), consistent with Prisma |
| Auth | `/api/auth/{login,register,logout,me,forgot-password}`, bearer token |
| Billing | Stripe: `/api/stripe/{checkout,checkout-concierge,portal}` |
| Data API | `/api/cars?make=&page=&limit=200`, `/api/cars/<id>`, `/api/cars/signals`, `/api/cars/images`, `/api/market-indexes`, `/api/market-deals`, `/api/price-drops`, `/api/picks`, `/api/benchmarks`, `/api/stats/public` |
| User features | `/api/garage`, `/api/watchlist`, `/api/alerts`, `/api/notifications`, `/api/upload/token` |
| Other | `/api/track` (analytics), `/api/booking/reserve`, `/api/concierge`, `/api/newsletter`, `/api/feature-requests`, Google Ads tag `AW-18164020872` |
| Env flag | `BACKTEST_RAW_MOVE=1` turns off the appreciation shrink (a backtesting mode) |

Public pages (`/cars/<make>/<model>/<year>`, `/market-trends`, `/appreciation`, …) are SEO
landing pages. Each embeds schema.org `Car`/`Product` JSON-LD with value, median, P25/P75,
min/max, sales count, 12-month change and average mileage.

## 3. Data pipeline (from /methodology plus page data)

1. **Collect** completed sales daily from 25 auction houses and marketplaces. Each record has
   a sold price, sale date and source URL, plus mileage, transmission, colours and equipment when
   published. Asking prices are stored separately as listings and never enter a value.
2. **Verify:** reserve-not-met lots are kept as bids and excluded (318k results become 258k sales;
   210k are clean USD sales).
3. **Clean:** exclude accident/salvage history, replicas and tributes, mislisted higher-spec
   variants, non-US sales, and "prices far outside the model's own distribution". In the bundle
   these appear as per-sale flags: `isOutlier`, `carfaxDamage`, `nonUsSale`, `reserveNotMet`.
4. **Value** each model-year from its own sales: normalise to typical mileage, weight by
   recency, bound against outliers. With too few clean sales the car shows "Limited Data".
5. **Recompute twice a day.**

## 4. Published statistics (reproduced exactly: `estimators.py` Part A)

| Number | Definition |
|---|---|
| Median sale | median of clean USD sales |
| Typical range | P25 to P75 of clean USD sales, shown only when n ≥ 8 |
| Price history by year | median per calendar year, years with n ≥ 3 |
| 12-month change | median(last 12 mo) / median(prior 12 mo) − 1, each window n ≥ 3; falls back to 1–3 years ago |
| Long-run trend ("+24.3%/yr since 2024") | annualised gain since the first US sale the value is computed from |

Check against the GT350R page: "10 sold in the past 12 months" matches the listed sales
exactly. The +19.8% change implies a prior-year median of about $96k, which sits inside the
visible prior-year sales.

## 5. Client-side math (exact port: `client_math.py`)

### 5.1 Collectibility score (1–10)
Start at 5, then:
* model tier: ultra-rare list +4 · track-focused +3 · performance +2 · mass-production SUV/sedan −2
* manual / 6-speed +1
* value > $500k +2 · > $200k +1 · < $30k −1
* value/MSRP > 1.5 +2 · > 1.1 +1
* age 20–35 +1 · age ≥ 40 +1
* brand: Ferrari/Porsche/Lamborghini/Bugatti/Pagani/Koenigsegg/McLaren/Aston +1 · Maserati/Jaguar/Land Rover −1
* clamp to [1, 10]. A **curated table of about 120 models overrides** the computed score
  (longest substring match wins, e.g. `MUSTANG SHELBY GT350R` = 9, `F40` = 10, `GT3` = 8).

### 5.2 Blended annual rate (projection driver)
Five factors:

| Factor | Formula |
|---|---|
| g, data trend | server `annualReturn` (long-run %/yr) |
| b, collectibility | (score − 5) × 1%, capped at ≤ 0 when age ≤ 5 |
| x, age | ≤2y −10%, ≤5y −6%, ≤10y −2%, ≤20y +1%, ≤35y +3%, else +4%, raised to a floor of +2% / −2% (age > 6, score ≥8 / ≥6) or −3% / −4% (age ≤ 6) |
| f, MSRP | value/MSRP > 2: +3% · > 1.2: +2% · > 0.8: −1% · > 0.5: −2% · else +1% |
| v, momentum | appreciating +2% · bottomed +3% · near bottom +1% · depreciating −2% · stable 0 |

Weights `(g, b, x, f, v)` depend on the signal and the evidence:

| Case | Weights |
|---|---|
| appreciating / depreciating | .65 .13 .12 .06 .04 |
| near bottom | .55 .15 .13 .10 .07 |
| n ≥ 25 and confidence > .5 | .50 .20 .10 .10 .10 |
| n ≥ 10 | .35 .25 .15 .15 .10 |
| otherwise | .20 .30 .25 .15 .10 |

The result is clamped to `[−6% | −10% | −15%, +14% | +12% | +10% | +8%]` by collectibility.
For falling cars with g ≤ −3%: rate = min(rate, k·g), with k = .34 (near bottom), .65
(age ≤ 5) or .5. **Dampening** (yearly decay of the rate): .94 / .90 / .85 / .82 by score, or
.62 / .70 / .78 when the rate is below −5%. **Floor** = 40% of today's value.

### 5.3 Value path
* **Rising or stable cars:** yearly compounding. The rate starts at max(1.2%, rate) for
  appreciating, max(2.6%, rate) for bottomed, or at least ±1.8% otherwise. Each year it
  multiplies by the dampening factor, with a magnitude floor of 1.2%.
* **Falling cars** (depreciating / near bottom, or a negative blended rate): a
  **quarterly** model. The decline rate is `blend(rate, recentReturn)`, scaled ×0.35 if
  age > 5. The quarterly rate decays by
  `(clamp(.76 − 2.2·(clamp(|o|,.02,.16) − .02), .45, .76) × (1 | .65))^¼`.
  The car "bottoms" once the annualised decline falls below max(0.6%, 0.35·|o|). After that
  it recovers at 1.5%/yr, capped at 60% of the drop. This yields the **estimated
  market-bottom date and value** (a Collector feature).
* **Appreciation shrink:** for appreciating cars only 25–30% of the modelled gain is shown
  (`0.3` if score ≥ 8, else `0.25 − 0.2·clamp((g−.08)/.06)`). The unshrunk path is exposed as
  `momentum3y/5y`.

### 5.4 Scenario bands
`u = max(0.15, 1 − confidence)` (confidence defaults to 0.3 if missing)
* 3y: bear = max(bottom, base·(0.92 − 0.15u)), bull = base·(1.10 + 0.18u)
* 5y: bear = max(bottom, base·(0.88 − 0.22u)), bull = base·(1.15 + 0.28u)
* Displayed confidence: 3y = 100·conf %, 5y = 80·conf %

### 5.5 Mileage adjustment
`o = (miles − avgMiles) / max(avgMiles, 5000)`. Below-average miles earn a piecewise-linear
premium: 5%·|o| up to |o| = .15, then steeper slopes (.15, .3, .6). Slopes scale with
collectibility (×1.5 / 1.2 / 1 / 0.7), age multiplies the upper bands (×1.1 / 1.3 / 1.5 for
10 / 20 / 30+ years), and odometers ≤ 500 mi get ×1.25 (≤ 1,000 mi: ×1.1). Above-average miles
take a gentler discount (2%·|o| …, −13% at 3× the average, a further −10% per extra multiple
of the average). The total is
clamped to −25…−30% / +15…+45% by collectibility.

### 5.6 Listing Analyzer and deal score
1. `adj = mileageAdjust(value, listingMiles, avgMiles)`
2. Dealer premium (retail over auction), linear between knots
   `$25k → 10%, $75k → 0%, $150k → 7.5%, $350k → 4.5%, $500k+ → 9%`
3. `fairAsk = adj × (1 + premium)`, `diff = (ask − fairAsk)/fairAsk`
4. Verdict: ≤ −12% **Great deal** · ≤ −4% Below market · ≤ +6% Fair · ≤ +15% Above market · else Overpriced
5. `dealScore = clamp(55 − 250·diff, 5, 98)`
6. Sold results: < −4% Below Market, > +6% Above Market

### 5.7 Data-strength badge
`score = .40·size + .35·clamp((fit − .1)/.35) + .25·dispersion`, where size steps over
n = 3/5/8/12/20 and dispersion is best at ≤ .18. High ≥ .62, Moderate ≥ .36; High drops to
Moderate if n < 12 or dispersion > .4; n < 4 is always Low. (The input names *fit* and
*dispersion* are inferred from the breakpoints.)

### 5.8 Sellability (months of supply)
`months = listings / max(0.5, sales24m/2) × 12`. Fewer than 4 sales in 24 months: thin market.
1 listing or fewer: tight supply. Under 6 months: seller's market. Up to 18: balanced.
Above 18: buyer's market.

### 5.9 Other scores
* Desirability / liquidity / resale (base 50 each, signal ± 10–20, miles < 10k +15, > 50k −10,
  MSRP > $200k +10, liquidity from sample size + recent sales + confidence, resale +100×annual return).
* "Best buys" rank = signal weight (2.5 / 2 / 1 / 0.4 / 0) + 10·clamp(annRet) + 6·clamp(recentRet)
  + min(1.5, n/40) + 1.5·confidence, with returns clamped to [−15%, +25%].
* Seasonality copy: buy discount = 1 − index(best month), sell premium = index(worst) − 1;
  strength ≥ 15% strong, ≥ 7% moderate. Needs 20+ sales across 4+ months over 1.5+ years.
* The price chart uses a Gaussian kernel smoother (bandwidth = span/8, clamped to 20–90 days)
  drawn as a cubic Bézier.

### 5.10 Option premiums
The "spec engine" mock-ups on the homepage come with a **static lookup table** in the bundle
(e.g. GT3 manual +10–15%, PTS +8–15%, Weissach +8–12%) for about 30 model families plus brand
defaults. Real measured premiums ("with-versus-without comparisons of real sales") come from
the server.

## 6. Server-side reconstruction (`estimators.py` Part B, inference)

* **Market value:** each sale is normalised to the model's median mileage by inverting the
  client mileage curve. Weights decay exponentially (half-life 365 d) and the last 5 sales count
  double. The value is the weighted median, bounded to P25–P75. GT350R with 15 of 78 sales:
  **$111,402 against the site's $114,593**.
* **Value Signal:** OLS of log(normalised price) on time gives `annualReturn`. The 12-month
  median change gives `recentReturn`. Confidence comes from R², sample size and CV, capped by
  sample size (n < 8 → 0.3, < 15 → 0.5, < 25 → 0.7). Classification thresholds are ±3%/yr.
  All of these constants are assumptions; DriveIndex doesn't publish them.

## 7. Product and pricing (from the page copy)

Free (values, garage, sale dates with prices locked) · **Pro $19.99/mo** (sold prices, Value
Signal + confidence, projections, alerts) · **Collector $39.99/mo** (Listing Analyzer, Deal Radar,
seasonality, bottom dates, option premiums, "Rad's Market Update") · **Dealer $499/mo** ·
Concierge $299 / $500 / $2,000.

Note: projections and option tables ship to every visitor's browser. Only the inputs
(`annualReturn`, `confidence`, `signal`, sold prices) are gated by the API.

## 8. Limits

* The Value Signal classifier, outlier thresholds, the exact market-value estimator and the
  seasonality decomposition are server-side and were not observed. Part B is a reconstruction.
* The bundle is a snapshot (`dpl_Eu5aFvEGZiXEmJ41x2ihPzoRdALQ`). Constants may change on
  any deploy.
* Reusing DriveIndex's data or code commercially raises legal questions (their terms,
  copyright). This repo contains an independent re-implementation and short descriptions,
  not their source files.
