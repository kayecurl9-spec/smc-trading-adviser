"""
fetch_data.py — Binance multi-timeframe klines fetcher for SMC skill
No API key required.

Usage:
python fetch_data.py --symbols btcusdt,ethusdt,solusdt,xrpusdt
https://raw.githubusercontent.com/kayecurl9-spec/smc-trading-adviser/main/smc_data.json
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone


BINANCE_URL = "https://api.binance.com/api/v3/klines"
MAX_PER_REQUEST = 1000
RATE_LIMIT_PAUSE = 0.25

COLUMNS = ["open_time", "open", "high", "low", "close", "volume",
           "close_time", "quote_volume", "trades",
           "taker_buy_base_vol", "taker_buy_quote_vol", "ignore"]


def fetch_klines(symbol: str, interval: str, limit: int) -> list[dict]:
    """Fetch up to `limit` candles for symbol/interval from Binance public API."""
    symbol = symbol.upper()
    all_candles: list[list] = []
    remaining = limit
    end_time: int | None = None

    while remaining > 0:
        batch = min(remaining, MAX_PER_REQUEST)
        params = f"symbol={symbol}&interval={interval}&limit={batch}"
        if end_time is not None:
            params += f"&endTime={end_time}"

        url = f"{BINANCE_URL}?{params}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                raw: list[list] = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            raise RuntimeError(f"Binance API error {e.code} for {symbol}: {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error fetching {symbol}: {e.reason}") from e

        if not raw:
            break

        all_candles = raw + all_candles
        remaining -= len(raw)

        if len(raw) < batch:
            break

        end_time = raw[0][0] - 1

        if remaining > 0:
            time.sleep(RATE_LIMIT_PAUSE)

    all_candles = all_candles[-limit:]
    return [_parse_candle(c) for c in all_candles]


def _parse_candle(raw: list) -> dict:
    return {
        "open_time":            raw[0],
        "open_time_utc":        _ts(raw[0]),
        "open":                 float(raw[1]),
        "high":                 float(raw[2]),
        "low":                  float(raw[3]),
        "close":                float(raw[4]),
        "volume":               float(raw[5]),
        "close_time":           raw[6],
        "close_time_utc":       _ts(raw[6]),
        "quote_volume":         float(raw[7]),
        "trades":               int(raw[8]),
        "taker_buy_base_vol":   float(raw[9]),
        "taker_buy_quote_vol":  float(raw[10]),
    }


def _ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Binance multi-timeframe OHLCV data for SMC analysis"
    )
    parser.add_argument(
        "--symbols", required=True,
        help="Comma-separated symbols, e.g. btcusdt,ethusdt,solusdt"
    )

    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    # Define timeframes: (interval, limit, description)
    timeframes = [
        ("15m", 50, "15 minutes"),
        ("1h", 12, "1 hour"),
        ("1d", 1, "1 day")
    ]

    # Single JSON structure
    all_data = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "symbols": symbols,
        "timeframes": {
            "15m": {"interval": "15m", "limit": 50},
            "1h": {"interval": "1h", "limit": 12},
            "1d": {"interval": "1d", "limit": 1}
        },
        "data": {}
    }

    for sym in symbols:
        print(f"\nFetching data for {sym}...", file=sys.stderr)
        symbol_data = {}

        for interval, limit, desc in timeframes:
            print(f"  → {desc} ({interval}) x{limit}...", file=sys.stderr)
            try:
                candles = fetch_klines(sym, interval, limit)
                symbol_data[interval] = candles
                print(f"    ✓ {len(candles)} candles", file=sys.stderr)
            except RuntimeError as e:
                print(f"    ✗ {e}", file=sys.stderr)
                symbol_data[interval] = []

        all_data["data"][sym] = symbol_data

    # Save to single JSON file
    filename = "smc_data.json"
    with open(filename, "w") as f:
        json.dump(all_data, f, indent=2)
    
    print(f"\n✓ Saved all data to {filename}", file=sys.stderr)
    print(f"  Symbols: {', '.join(symbols)}", file=sys.stderr)
    print(f"  Timeframes: 15m (50), 1h (12), 1d (1)", file=sys.stderr)


if __name__ == "__main__":
    main()