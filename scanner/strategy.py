"""Position sizing and risk-rule calculations for the bullish scanner strategy."""

import math

ALLOCATION_PER_POSITION = 500.0
TAKE_PROFIT_MULTIPLIER = 1.10


def build_signal(ticker, pattern, signal_candle, entry_price=None,
                  allocation=ALLOCATION_PER_POSITION, available_cash=None):
    """signal_candle is a row with .high/.low/.close (the confirmed daily candle).
    entry_price defaults to the signal candle's close ("Close" entry mode);
    pass the next session's open for "Next Open" entry mode.
    available_cash, if given, caps allocation to whatever buying power is
    actually left (a live account may have less than `allocation` free)."""
    entry = float(entry_price if entry_price is not None else signal_candle.close)
    day_high = float(signal_candle.high)
    day_low = float(signal_candle.low)
    effective_allocation = allocation if available_cash is None else min(allocation, available_cash)
    shares = math.floor(effective_allocation / entry) if entry > 0 else 0
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


def build_morning_star_signal(ticker, day1, day2, day3, pattern_low, entry_price=None,
                               allocation=ALLOCATION_PER_POSITION, available_cash=None,
                               entry_mode="eod_confirmed"):
    """day1/day2/day3 are the three pattern candles (.open/.high/.low/.close);
    pattern_low is min(day1.low, day2.low, day3.low) — the Morning Star's
    stop-loss reference, distinct from the generic single-day-low stop
    used elsewhere. entry_price defaults to Day 3's close ("Close" entry
    mode); pass Day 4's open for "Next Open" entry mode.
    entry_mode: 'eod_confirmed' (Day 3 is a completed bar — the pattern is
    fully confirmed) or 'intraday_probable' (Day 3 is still forming; day3
    and pattern_low reflect a snapshot near close, not the final settled
    values — see patterns.morning_star_day3_probable). Always record which
    one produced a given position so the report is honest about confidence."""
    entry = float(entry_price if entry_price is not None else day3.close)
    effective_allocation = allocation if available_cash is None else min(allocation, available_cash)
    shares = math.floor(effective_allocation / entry) if entry > 0 else 0
    target = round(entry * TAKE_PROFIT_MULTIPLIER, 2)

    return {
        "ticker": ticker,
        "pattern": "Morning Star",
        "entry_mode": entry_mode,
        "day1_close": round(float(day1.close), 2),
        "day2_low": round(float(day2.low), 2),
        "day3_close": round(entry, 2),
        "entry_price": round(entry, 2),
        "shares": shares,
        "stop_loss": round(float(pattern_low), 2),
        "target_price": target,
    }


def build_three_red_reversal_signal(ticker, day1, day2, day3, day4, pattern_low, entry_price=None,
                                     allocation=ALLOCATION_PER_POSITION, available_cash=None,
                                     entry_mode="eod_confirmed"):
    """day1/day2/day3 are the three red (bearish) days; day4 is today's
    green (bullish) confirmation day. pattern_low is the lowest low across
    all 4 days — the stop-loss reference. entry_price defaults to Day 4's
    close ("Close" entry mode); pass Day 5's open for "Next Open" mode.
    entry_mode: 'eod_confirmed' (Day 4 is a completed bar) or
    'intraday_probable' (Day 4 is still forming — see
    patterns.three_red_reversal_day4_probable)."""
    entry = float(entry_price if entry_price is not None else day4.close)
    effective_allocation = allocation if available_cash is None else min(allocation, available_cash)
    shares = math.floor(effective_allocation / entry) if entry > 0 else 0
    target = round(entry * TAKE_PROFIT_MULTIPLIER, 2)

    return {
        "ticker": ticker,
        "pattern": "Three Red Days Reversal",
        "entry_mode": entry_mode,
        "day1_close": round(float(day1.close), 2),
        "day2_close": round(float(day2.close), 2),
        "day3_close": round(float(day3.close), 2),
        "day4_close": round(entry, 2),
        "entry_price": round(entry, 2),
        "shares": shares,
        "stop_loss": round(float(pattern_low), 2),
        "target_price": target,
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
