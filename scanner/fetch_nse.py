"""Fetch NSE live-analysis data: 52-week highs, volume gainers, price gainers.

Verified field names (as of Aug 2026):
  52W high row:      symbol, series, comapnyName (NSE's typo), ltp, pChange,
                     new52WHL, prev52WHL, prevHLDate, prevClose, change
  Volume gainer row: symbol, companyName, volume, week1AvgVolume, week1volChange,
                     week2AvgVolume, week2volChange, ltp, pChange, turnover (LAKHS)
  Price gainer:      top-level keys NIFTY/BANKNIFTY/.../allSec; allSec.data rows:
                     symbol, series, open_price, high_price, low_price, ltp,
                     prev_price, perChange, trade_quantity, turnover (LAKHS)
"""
import json
import random
import time
from pathlib import Path

import requests

BASE = "https://www.nseindia.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

ENDPOINTS = {
    "high52w": {
        "url": f"{BASE}/api/live-analysis-data-52weekhighstock",
        "referer": f"{BASE}/market-data/52-week-high-equity-market",
    },
    "volume_gainers": {
        "url": f"{BASE}/api/live-analysis-volume-gainers",
        "referer": f"{BASE}/market-data/volume-gainers-spurts",
    },
    "price_gainers": {
        "url": f"{BASE}/api/live-analysis-variations?index=gainers",
        "referer": f"{BASE}/market-data/top-gainers-losers",
    },
}


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    })
    # Cookie bootstrap. NSE sometimes 403s the homepage but still serves the
    # API, so failures here are non-fatal.
    for url in (BASE, ENDPOINTS["high52w"]["referer"]):
        try:
            s.get(url, timeout=12)
        except requests.RequestException:
            pass
        time.sleep(0.5 + random.random())
    return s


def fetch_endpoint(name: str, session: requests.Session, retries: int = 4):
    ep = ENDPOINTS[name]
    for attempt in range(retries):
        try:
            r = session.get(ep["url"], headers={"Referer": ep["referer"]}, timeout=25)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                return r.json()
            print(f"  [{name}] attempt {attempt + 1}: HTTP {r.status_code}")
        except requests.RequestException as e:
            print(f"  [{name}] attempt {attempt + 1}: {type(e).__name__}")
        time.sleep(3 + attempt * 4 + random.random() * 2)
        if attempt == retries - 2:  # fresh cookies before the last try
            session = new_session()
    return None


def fetch_all(raw_dir: Path) -> dict:
    """Fetch all three feeds. Returns {name: json_or_None} and archives raw JSON."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = new_session()
    out = {}
    for name in ENDPOINTS:
        js = fetch_endpoint(name, session)
        out[name] = js
        if js is not None:
            (raw_dir / f"{name}.json").write_text(
                json.dumps(js, indent=1), encoding="utf-8")
            n = len(js.get("data", js.get("allSec", {}).get("data", []) or []))
            print(f"  [{name}] OK — {n} rows, timestamp: "
                  f"{js.get('timestamp', js.get('allSec', {}).get('timestamp', '?'))}")
        else:
            print(f"  [{name}] FAILED after retries")
        time.sleep(1 + random.random())
    return out
