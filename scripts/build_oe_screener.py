#!/usr/bin/env python3
"""Build OE Yield screener data from estimates.json + live FMP prices."""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
ESTIMATES_PATH = os.path.join(PROJECT_ROOT, "oe-yield", "estimates.json")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "oe-yield", "data.json")

FMP_API_KEY = os.environ.get("FMP_API_KEY", "ssw62N6jj7yprzsNsNdCIxTJ4aQ9mtew")
FMP_URL = "https://financialmodelingprep.com/stable/profile?symbol={ticker}&apikey={key}"


# --- Pure calculation functions ---

def calc_oe_yield(oe_per_share, price):
    """OE Yield = oePerShare / currentPrice * 100. Returns None if price is 0."""
    if price == 0:
        return None
    return oe_per_share / price * 100


def calc_blended_growth(g1, g2, phase1_years=10, total_years=30):
    """Blended growth = (phase1 * g1 + phase2 * g2) / total."""
    phase2_years = total_years - phase1_years
    return (phase1_years * g1 + phase2_years * g2) / total_years


def calc_expected_return(oe_yield, blended_growth):
    """Expected return = OE Yield + Blended Growth."""
    return oe_yield + blended_growth


def filter_usd_only(entries):
    """Filter out entries that have a currency field set (non-USD)."""
    return [e for e in entries if "currency" not in e]


def filter_all(entries):
    """Return all entries regardless of currency."""
    return list(entries)


CURRENCY_SYMBOLS = {
    "USD": "$",
    "GBp": "£",
    "GBP": "£",
    "JPY": "¥",
    "EUR": "€",
    "CAD": "C$",
    "AUD": "A$",
    "CHF": "CHF ",
    "BRL": "R$",
}


def currency_symbol(code):
    """Map currency code to display symbol. Unknown codes return 'CODE '."""
    return CURRENCY_SYMBOLS.get(code, code + " ")


def _parse_fmp_response(data):
    """Extract price from FMP API response. Returns None if unavailable."""
    if not data or not isinstance(data, list) or len(data) == 0:
        return None
    return data[0].get("price")


def build_output_entry(estimate, price):
    """Build a single output entry from an estimate dict and a price."""
    oe_yield = calc_oe_yield(estimate["oePerShare"], price)
    blended = calc_blended_growth(estimate["g1"], estimate["g2"])
    expected = calc_expected_return(oe_yield, blended)
    cur = estimate.get("currency", "USD")
    return {
        "ticker": estimate["ticker"],
        "company": estimate["company"],
        "businessType": estimate["businessType"],
        "oePerShare": estimate["oePerShare"],
        "currentPrice": price,
        "currency": cur,
        "currencySymbol": currency_symbol(cur),
        "oeYield": round(oe_yield, 2),
        "g1": estimate["g1"],
        "g2": estimate["g2"],
        "blendedGrowth": round(blended, 2),
        "expectedReturn": round(expected, 2),
        "durability": estimate.get("durability", "TBD"),
        "estimateDate": estimate["estimateDate"],
        "notes": estimate.get("notes", ""),
    }


# --- I/O functions ---

def fetch_price(ticker):
    """Fetch current price from FMP API. Returns None on failure."""
    url = FMP_URL.format(ticker=ticker, key=FMP_API_KEY)
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return _parse_fmp_response(data)
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        print(f"  Warning: could not fetch price for {ticker}: {e}", file=sys.stderr)
        return None


def main():
    with open(ESTIMATES_PATH, "r") as f:
        estimates = json.load(f)

    all_estimates = filter_all(estimates)
    print(f"Processing {len(all_estimates)} estimates")

    results = []
    for est in all_estimates:
        ticker = est["ticker"]
        cur = est.get("currency", "USD")
        sym = currency_symbol(cur)
        print(f"  Fetching {ticker} ({cur})...", end=" ")
        price = fetch_price(ticker)
        if price is None:
            print("SKIPPED (no price)")
            continue
        entry = build_output_entry(est, price)
        print(f"{sym}{price:,.2f} → OE Yield {entry['oeYield']:.1f}%, "
              f"Expected Return {entry['expectedReturn']:.1f}%")
        results.append(entry)

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "entries": results,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote {len(results)} entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
