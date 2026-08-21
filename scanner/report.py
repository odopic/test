"""Renders the two required markdown report tables."""

ACTION_LABELS = {
    "HOLD": "Hold",
    "SELL_STOP": "Sell Stop",
    "SELL_TARGET": "Sell Target",
    "DATA_MISSING": "DATA DELAYED/INCOMPLETE",
}


def render_scan_table(signals):
    lines = [
        "| Ticker | Pattern Detected | Entry Price | Signal Day High | "
        "Signal Day Low (Stop Loss) | Shares ($500 Budget) | Target Price (+10%) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    if not signals:
        lines.append("| _None_ | No confirmed bullish setups today | | | | | |")
        return "\n".join(lines)
    for s in signals:
        lines.append(
            f"| {s['ticker']} | {s['pattern']} | ${s['entry_price']:.2f} | "
            f"${s['signal_day_high']:.2f} | ${s['signal_day_low']:.2f} | "
            f"{s['shares']} shares | ${s['target_price']:.2f} |"
        )
    return "\n".join(lines)


def render_positions_table(rows):
    lines = [
        "| Ticker | Entry Date | Entry Price | Shares | Current Price | "
        "Stop-Loss Level | Target (+10%) | Unrealized P&L (%) | "
        "Action (Hold / Sell Stop / Sell Target) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    if not rows:
        lines.append("| _None_ | No open positions | | | | | | | |")
        return "\n".join(lines)
    for r in rows:
        price = "DELAYED" if r["current_price"] is None else f"${r['current_price']:.2f}"
        pnl = "N/A" if r["unrealized_pct"] is None else f"{r['unrealized_pct']:+.1f}%"
        lines.append(
            f"| {r['ticker']} | {r['entry_date']} | ${r['entry_price']:.2f} | "
            f"{r['shares']} | {price} | ${r['stop_loss']:.2f} | "
            f"${r['target_price']:.2f} | {pnl} | {ACTION_LABELS[r['action']]} |"
        )
    return "\n".join(lines)


def render_report(date, signals, position_rows, flagged_tickers=None):
    parts = [
        f"# NASDAQ Bullish Scanner Report — {date}",
        "",
        "## 1. Daily Scan & New Buy Signals",
        render_scan_table(signals),
        "",
        "## 2. Open Positions & Monitoring Status",
        render_positions_table(position_rows),
    ]
    if flagged_tickers:
        parts += ["", "## Data Quality Flags",
                   "\n".join(f"- {t}: delayed or incomplete market data" for t in flagged_tickers)]
    return "\n".join(parts)


def render_morning_star_scan_table(signals):
    lines = [
        "| Ticker | Day 1 Close | Day 2 Low (Base Stop) | Day 3 Close (Entry) | "
        "Shares ($500 Budget) | Stop Loss ($) | Target (+10%) ($) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    if not signals:
        lines.append("| _None_ | No confirmed Morning Star setups today | | | | | |")
        return "\n".join(lines)
    for s in signals:
        ticker_label = s["ticker"]
        if s.get("entry_mode") == "intraday_probable":
            ticker_label += " ⚠︎"
        lines.append(
            f"| {ticker_label} | ${s['day1_close']:.2f} | ${s['day2_low']:.2f} | "
            f"${s['day3_close']:.2f} | {s['shares']} shares | ${s['stop_loss']:.2f} | "
            f"${s['target_price']:.2f} |"
        )
    if any(s.get("entry_mode") == "intraday_probable" for s in signals):
        lines.append("")
        lines.append("⚠︎ = intraday entry ~15 min before close, on an UNCONFIRMED "
                      "still-forming Day 3 candle (heuristic probability estimate, "
                      "not a settled close). Day 3 Close and Stop Loss are a "
                      "near-close snapshot, not final values.")
    return "\n".join(lines)


_PORTFOLIO_ACTION_LABELS = {
    "HOLD": "HOLD",
    "SELL_STOP": "SELL (Stop)",
    "SELL_TARGET": "SELL (Target)",
    "DATA_MISSING": "DATA DELAYED/INCOMPLETE",
}


def render_portfolio_table(rows):
    lines = [
        "| Ticker | Entry Date | Entry Price | Shares | Current Price | "
        "Stop Loss Level | Target (+10%) | Unrealized P&L (%) | Action |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    if not rows:
        lines.append("| _None_ | No open positions | | | | | | | |")
        return "\n".join(lines)
    for r in rows:
        price = "DELAYED" if r["current_price"] is None else f"${r['current_price']:.2f}"
        pnl = "N/A" if r["unrealized_pct"] is None else f"{r['unrealized_pct']:+.1f}%"
        lines.append(
            f"| {r['ticker']} | {r['entry_date']} | ${r['entry_price']:.2f} | "
            f"{r['shares']} | {price} | ${r['stop_loss']:.2f} | "
            f"${r['target_price']:.2f} | {pnl} | {_PORTFOLIO_ACTION_LABELS[r['action']]} |"
        )
    return "\n".join(lines)


def render_morning_star_report(date, signals, position_rows, flagged_tickers=None):
    parts = [
        f"# NASDAQ Morning Star Scanner Report — {date}",
        "",
        "## 1. Confirmed Morning Star Signals (New Buys)",
        render_morning_star_scan_table(signals),
        "",
        "## 2. Portfolio Tracking Table",
        render_portfolio_table(position_rows),
    ]
    if flagged_tickers:
        parts += ["", "## Data Quality Flags",
                   "\n".join(f"- {t}: delayed or incomplete market data" for t in flagged_tickers)]
    return "\n".join(parts)


def render_three_red_scan_table(signals):
    lines = [
        "| Ticker | Day 1 Close | Day 2 Close | Day 3 Close | Day 4 Close (Entry) | "
        "Shares ($500 Budget) | Stop Loss ($) | Target (+10%) ($) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    if not signals:
        lines.append("| _None_ | No confirmed setups today | | | | | | |")
        return "\n".join(lines)
    for s in signals:
        ticker_label = s["ticker"]
        if s.get("entry_mode") == "intraday_probable":
            ticker_label += " ⚠︎"
        lines.append(
            f"| {ticker_label} | ${s['day1_close']:.2f} | ${s['day2_close']:.2f} | "
            f"${s['day3_close']:.2f} | ${s['day4_close']:.2f} | {s['shares']} shares | "
            f"${s['stop_loss']:.2f} | ${s['target_price']:.2f} |"
        )
    if any(s.get("entry_mode") == "intraday_probable" for s in signals):
        lines.append("")
        lines.append("⚠︎ = intraday entry ~15 min before close, on an UNCONFIRMED "
                      "still-forming Day 4 candle (heuristic estimate, not a settled close).")
    return "\n".join(lines)


def render_three_red_reversal_report(date, signals, position_rows, flagged_tickers=None):
    parts = [
        f"# NASDAQ Three-Red-Days Reversal Scanner Report — {date}",
        "",
        "## 1. Confirmed Bullish Reversal Signals (New Buys)",
        render_three_red_scan_table(signals),
        "",
        "## 2. Portfolio Tracking Table",
        render_portfolio_table(position_rows),
    ]
    if flagged_tickers:
        parts += ["", "## Data Quality Flags",
                   "\n".join(f"- {t}: delayed or incomplete market data" for t in flagged_tickers)]
    return "\n".join(parts)
