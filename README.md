# Driveindex

A reverse-engineered model of [driveindex.com](https://driveindex.com)'s collector-car valuation
math, captured with [REA (Reverse Engineer Anything)](https://github.com/morluto/rea).

* **Report:** [docs/REVERSE_ENGINEERING_REPORT.md](docs/REVERSE_ENGINEERING_REPORT.md)
* **Client-side math, exact port:** [driveindex_model/client_math.py](driveindex_model/client_math.py):
  projections with bear/base/bull bands, collectibility score, mileage curve, dealer premium,
  Listing Analyzer verdicts, deal score, data-strength badge, sellability
* **Server-side statistics:** [driveindex_model/estimators.py](driveindex_model/estimators.py):
  published rules (median, P25–P75, yearly medians, 12-month change) plus a reconstructed
  market-value estimator and Value Signal
* **Capture:** [scripts/rea_capture.sh](scripts/rea_capture.sh)

```bash
pip install pytest
pytest            # 2,404 tests, including parity with the original JS on 2,400 random cases
```

```python
from driveindex_model import project, analyze_listing
p = project(value=114_593, annual_return=0.12, confidence=0.35, sample_size=78,
            signal="appreciating", year=2020, make="Ford", model="Mustang Shelby GT350R",
            msrp=74_055, recent_return=0.136)
print(p.forecast3y, p.bear3y, p.bull3y)
print(analyze_listing(ask=89_985, market_value=114_593, miles=9_182, avg_miles=3_005,
                      collect_score=9, age=6))
```
