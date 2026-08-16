"""Position sizing and risk-rule calculations for the bullish scanner strategy."""

import math

ALLOCATION_PER_POSITION = 500.0
TAKE_PROFIT_MULTIPLIER = 1.20


def build_signal(ticker, pattern, signal_candle, entry_price=None,
                  allocation=ALLOCATION_PER_POSITION):
    """signal_candle is a row with .high/.low/.close (the confirmed daily candle).
    entry_price defaults to the signal candle's close ("Close" entry mode);
    pass the next session's open for "Next Open" entry mode."""
    entry = float(entry_price if entry_price is not None else signal_candle.close)
    day_high = float(signal_candle.high)
    day_low = float(signal_candle.low)
    shares = math.floor(allocation / entry) if entry > 0 else 0
    target = round(entry * TAKE_PROFIT_MULTIPLIER, 2)

    return {
        "ticker": ticker,
        "pattern": pattern,
        "entry_price": round(entry, 2),
        "signal_day_high": round(day_high, 2),
        "signal_day_low": round(day_low, 2),
        "shares": shares,
        "target_price": target,
        "stop_loss": round(day_low, 2),
    }


def evaluate_exit(position, current_price):
    """Return one of 'SELL_STOP', 'SELL_TARGET', or 'HOLD'."""
    if current_price <= position["stop_loss"]:
        return "SELL_STOP"
    if current_price >= position["target_price"]:
        return "SELL_TARGET"
    return "HOLD"


def unrealized_pct(position, current_price):
    entry = position["entry_price"]
    if entry <= 0:
        return 0.0
    return round((current_price - entry) / entry * 100, 2)
