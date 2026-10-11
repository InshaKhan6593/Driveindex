"""Parse a public driveindex.com car-year page into published figures + listed sales.

Usage: python -I scripts/parse_car_page.py page.html [...] > cars.json
"""

import html
import json
import re
import sys
from datetime import datetime


def _text(raw: str) -> str:
    raw = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _money(s):
    return int(s.replace("$", "").replace(",", "")) if s else None


def _props(raw: str) -> dict:
    for block in re.findall(r'<script type="application/ld\+json">([\s\S]*?)</script>', raw):
        try:
            d = json.loads(block)
        except ValueError:
            continue
        if isinstance(d, dict) and "Car" in (d.get("@type") or []):
            out = {p["name"]: p["value"] for p in d.get("additionalProperty", [])}
            out["name"] = d.get("name")
            out["url"] = d.get("url")
            return out
    return {}


def parse(raw: str) -> dict:
    t = _text(raw)
    p = _props(raw)
    res = {
        "name": p.get("name"),
        "url": p.get("url"),
        "market_value": p.get("Current market value (USD)"),
        "median": p.get("Median verified sale price (USD)"),
        "p25": p.get("Typical sale price, lower quartile (USD)"),
        "p75": p.get("Typical sale price, upper quartile (USD)"),
        "min": p.get("Lowest verified sale (USD)"),
        "max": p.get("Highest verified sale (USD)"),
        "sales_count": p.get("Verified auction sales tracked"),
        "sales_12m": p.get("Verified sales in the past 12 months"),
        "change_12m_pct": p.get(
            "Median sale price, past 12 months vs the prior year (percent difference)"),
        "avg_miles": p.get("Average mileage of sold examples"),
        "as_of": p.get("Market value as of"),
        "limited_data": "Limited Data" in t,
    }
    if res["market_value"] is None:
        # Stale cars ("No sale since ...") omit the value from JSON-LD but state it in text.
        m = re.search(r"has a (?:current )?market value of (\$[\d,]+)", t)
        res["market_value"] = _money(m.group(1)) if m else None
    res["stale"] = "No sale since" in t
    m = re.search(r"Original MSRP (\$[\d,]+)", t)
    res["msrp"] = p.get("Original MSRP (USD)") or (_money(m.group(1)) if m else None)
    m = re.search(r"latest sale ([A-Z][a-z]{2} \d{1,2}, \d{4})", t)
    res["latest_sale"] = (datetime.strptime(m.group(1), "%b %d, %Y").date().isoformat()
                          if m else None)
    if res["sales_count"] is None:
        m = re.search(r"based on (\d+) verified auction sales?", t)
        res["sales_count"] = int(m.group(1)) if m else None

    # Recent auction results table: "<date> $<price> <miles|—> <gearbox|—>"
    sales = []
    sec = t.split("Auction Results", 1)[1] if "Auction Results" in t else ""
    sec = sec.split("Verified results from", 1)[0]
    for m in re.finditer(
            r"([A-Z][a-z]{2} \d{1,2}, \d{4}) (\$[\d,]+)(?: \(([A-Z]{3}) ?[^)]*\))? "
            r"((?:[\d,]+ mi)|—|Mileage n/a)? ?(Manual|Automatic|—)?", sec):
        miles = m.group(4)
        sales.append({
            "date": datetime.strptime(m.group(1), "%b %d, %Y").date().isoformat(),
            "price": _money(m.group(2)),
            "miles": int(miles.replace(",", "").replace(" mi", "")) if miles and "mi" in miles
            and "n/a" not in miles else None,
            "gearbox": m.group(5) if m.group(5) not in (None, "—") else None,
        })
    res["listed_sales"] = sales

    hist = {}
    if "Price History" in t:
        h = t.split("Median sale Sales", 1)[1] if "Median sale Sales" in t else ""
        h = h.split("Years with fewer", 1)[0]
        for m in re.finditer(r"(\d{4}) (\$[\d,]+) (\d+)", h):
            hist[int(m.group(1))] = {"median": _money(m.group(2)), "n": int(m.group(3))}
    res["history_by_year"] = hist
    res["fully_listed"] = bool(res["sales_count"]) and len(sales) >= res["sales_count"]
    return res


if __name__ == "__main__":
    out = [parse(open(f, encoding="utf-8").read()) for f in sys.argv[1:]]
    json.dump(out, sys.stdout, indent=1)
