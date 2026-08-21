#!/usr/bin/env python3
"""NASDAQ bullish candlestick scanner.

Data-source agnostic: reads one CSV per ticker from --data-dir, each with
ascending-by-date columns: date,open,high,low,close,volume. Populate that
directory from whatever daily-bar source you have access to (broker API,
market-data vendor, etc.) and run this after the session confirms.

Usage:
    python run_scanner.py --data-dir data/daily --universe universe/nasdaq100.txt
"""

import argparse
import csv
import os
import sys
from datetime import date as date_cls

from scanner import patterns, portfolio, report, strategy


def load_ohlcv(csv_path):
    rows = []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            rows.append({
                "date": r["date"],
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r.get("volume") or 0),
            })
    rows.sort(key=lambda r: r["date"])
    return rows


class _Row:
    """Lightweight attribute-access wrapper so patterns.py can use dot access."""
    def __init__(self, d):
        self.__dict__.update(d)


class _Frame:
    """Minimal ascending OHLCV frame: only what patterns.detect() needs,
    no pandas dependency required."""
    def __init__(self, rows):
        self._rows = rows

    def __len__(self):
        return len(self._rows)

    @property
    def close(self):
        return [r["close"] for r in self._rows]

    def __getitem__(self, key):
        if key == "close":
            return self.close
        raise KeyError(key)

    class _ILoc:
        def __init__(self, rows):
            self._rows = rows

        def __getitem__(self, idx):
            return _Row(self._rows[idx])

    @property
    def iloc(self):
        return _Frame._ILoc(self._rows)


def read_universe(path):
    tickers = []
    with open(path) as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                tickers.append(line.upper())
    return tickers


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True,
                     help="Directory with <TICKER>.csv daily OHLCV files")
    ap.add_argument("--universe", default=os.path.join("universe", "nasdaq100.txt"))
    ap.add_argument("--portfolio", default="portfolio_state.json")
    ap.add_argument("--allocation", type=float, default=strategy.ALLOCATION_PER_POSITION)
    ap.add_argument("--downtrend-lookback", type=int, default=5)
    ap.add_argument("--entry-mode", choices=["close", "next_open"], default="close")
    ap.add_argument("--pattern", choices=["three_red", "morning_star", "any"], default="three_red",
                     help="'three_red' (default): three consecutive red days in a declining "
                          "staircase followed by a green day, stop-loss = 4-day pattern low. "
                          "'morning_star': strictly Morning Star only, stop-loss = 3-day pattern "
                          "low. 'any': the original 8-pattern scan with a single-day-low stop.")
    ap.add_argument("--report-date", default=None,
                     help="Label for the report; defaults to today's date")
    ap.add_argument("--reports-dir", default="reports")
    args = ap.parse_args()

    tickers = read_universe(args.universe)
    state = portfolio.load(args.portfolio)

    signals = []
    current_prices = {}
    flagged = []

    for ticker in tickers:
        csv_path = os.path.join(args.data_dir, f"{ticker}.csv")
        if not os.path.exists(csv_path):
            flagged.append(ticker)
            continue

        rows = load_ohlcv(csv_path)
        if not rows:
            flagged.append(ticker)
            continue

        current_prices[ticker] = rows[-1]["close"]

        if portfolio.is_held(state, ticker):
            continue  # never trigger a new buy signal on an already-open position

        frame = _Frame(rows)
        if args.pattern == "three_red":
            tr = patterns.detect_three_red_then_green(frame)
            if not tr:
                continue
            signal = strategy.build_three_red_reversal_signal(
                ticker, tr["day1"], tr["day2"], tr["day3"], tr["day4"], tr["pattern_low"],
                entry_price=None, allocation=args.allocation)
        elif args.pattern == "morning_star":
            ms = patterns.detect_morning_star(frame, downtrend_lookback=args.downtrend_lookback)
            if not ms:
                continue
            signal = strategy.build_morning_star_signal(
                ticker, ms["day1"], ms["day2"], ms["day3"], ms["pattern_low"],
                entry_price=None, allocation=args.allocation)
        else:
            pattern_name = patterns.detect(frame, downtrend_lookback=args.downtrend_lookback)
            if not pattern_name:
                continue
            signal_row = _Row(rows[-1])
            signal = strategy.build_signal(ticker, pattern_name, signal_row,
                                            entry_price=None, allocation=args.allocation)

        signals.append(signal)
        portfolio.open_position(state, signal, entry_date=rows[-1]["date"])

    position_rows = portfolio.evaluate_all(state, current_prices)
    portfolio.save(state, args.portfolio)

    report_date = args.report_date or date_cls.today().isoformat()
    if args.pattern == "three_red":
        text = report.render_three_red_reversal_report(report_date, signals, position_rows,
                                                         flagged_tickers=flagged)
    elif args.pattern == "morning_star":
        text = report.render_morning_star_report(report_date, signals, position_rows,
                                                   flagged_tickers=flagged)
    else:
        text = report.render_report(report_date, signals, position_rows, flagged_tickers=flagged)

    os.makedirs(args.reports_dir, exist_ok=True)
    out_path = os.path.join(args.reports_dir, f"{report_date}.md")
    with open(out_path, "w") as f:
        f.write(text + "\n")

    print(text)
    print(f"\n(report written to {out_path})", file=sys.stderr)


if __name__ == "__main__":
    main()
