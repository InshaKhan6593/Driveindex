"""Check the published-statistics rules against a live car page.

Data: https://driveindex.com/cars/ford/mustang-shelby-gt350r/2020 (fetched 2026-10-11).
The public page lists only the 15 most recent of 78 sales, so only figures that depend on
the last 12 months can be checked end-to-end.
"""

from datetime import date

from driveindex_model.client_math import analyze_listing, collectibility
from driveindex_model.estimators import Sale, twelve_month_change

AS_OF = date(2026, 10, 10)
RECENT = [  # (date, price, miles) as listed under "Recent ... Auction Results"
    (date(2026, 10, 10), 76_600, 17_000), (date(2026, 8, 7), 117_000, 1_200),
    (date(2026, 7, 2), 129_000, 30), (date(2026, 6, 3), 134_000, 458),
    (date(2026, 5, 16), 113_000, 7_000), (date(2026, 5, 15), 121_000, 3_400),
    (date(2026, 3, 22), 100_000, 861), (date(2026, 3, 21), 119_000, 2_900),
    (date(2026, 1, 28), 80_500, 20_000), (date(2025, 12, 4), 80_000, 22_000),
    (date(2025, 10, 4), 101_200, 1_946), (date(2025, 8, 27), 66_800, 14_900),
    (date(2025, 6, 27), 86_000, 7_000), (date(2025, 5, 31), 119_300, 16),
    (date(2025, 5, 24), 123_750, 9),
]
SALES = [Sale(d, p, m) for d, p, m in RECENT]


def test_sold_in_past_12_months_matches_page():
    # Page: "10 have sold in the past 12 months"
    n = sum(1 for s in SALES if (AS_OF - s.sold).days < 365)
    assert n == 10


def test_twelve_month_change_rule_is_consistent():
    # Page: +19.8%. Current-window median from the listed sales is 115,000, which implies a
    # prior-year median of ~96,000. The prior window is only partially listed, so check the
    # implied base is inside the range of the prior-window sales that are visible.
    cur_median = 115_000
    implied_prior = cur_median / 1.198
    visible_prior = [s.price for s in SALES if 365 <= (AS_OF - s.sold).days < 730]
    assert min(visible_prior) <= implied_prior <= max(visible_prior)
    change, basis = twelve_month_change(SALES, AS_OF)
    assert basis == "prior 12 months" and change > 0


def test_gt350r_is_curated_nine():
    col = collectibility("Ford", "Mustang Shelby GT350R", 2020, 114_593, 74_055, 2026)
    assert col.score == 9 and col.curated


def test_marketing_example_listing_verdict():
    # Homepage example: 2021 McLaren 765LT, ask $369,900 vs fair ask $420,400 -> "Great deal".
    v = analyze_listing(369_900, 420_400, value_is_listing_based=True)
    assert v.signal == "great" and v.fair_ask == 420_400
