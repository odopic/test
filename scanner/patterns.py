"""Bullish daily candlestick pattern detection.

Each detector takes a DataFrame of OHLCV rows (ascending by date, columns
open/high/low/close/volume) and looks only at the most recent 1-3 candles.
Detectors are geometry-only (no external TA library) so results are
reproducible against raw broker OHLCV data.
"""

from dataclasses import dataclass


@dataclass
class Candle:
    open: float
    high: float
    low: float
    close: float

    @property
    def body(self):
        return abs(self.close - self.open)

    @property
    def range(self):
        return max(self.high - self.low, 1e-9)

    @property
    def upper_shadow(self):
        return self.high - max(self.open, self.close)

    @property
    def lower_shadow(self):
        return min(self.open, self.close) - self.low

    @property
    def is_bullish(self):
        return self.close > self.open

    @property
    def is_bearish(self):
        return self.close < self.open

    @property
    def midpoint(self):
        return (self.open + self.close) / 2


def _candle(row):
    return Candle(row.open, row.high, row.low, row.close)


def is_downtrend(closes, lookback=5):
    """True if the close `lookback` sessions ago is above the most recent
    close among the candles preceding the signal (a simple net-decline check)."""
    if len(closes) < lookback + 1:
        return False
    prior = closes[-(lookback + 1):-1]
    return prior[-1] < prior[0]


PATTERN_PRIORITY = [
    "Three White Soldiers",
    "Morning Star",
    "Bullish Engulfing",
    "Piercing Line",
    "Bullish Harami",
    "Hammer",
    "Inverted Hammer",
    "Dragonfly Doji",
]


def detect(df, downtrend_lookback=5):
    """Return the highest-priority confirmed bullish pattern name for the
    last row of `df`, or None. `df` must have at least
    downtrend_lookback + 3 rows, ascending by date."""
    if len(df) < downtrend_lookback + 3:
        return None

    closes = list(df["close"])
    trend_closes = closes[:-1]  # everything up to (not including) the signal candle
    downtrend = is_downtrend(trend_closes, downtrend_lookback)

    c0 = _candle(df.iloc[-1])   # signal candle
    c1 = _candle(df.iloc[-2])   # day before
    c2 = _candle(df.iloc[-3])   # two days before

    checks = {
        "Three White Soldiers": _three_white_soldiers(c2, c1, c0, downtrend),
        "Morning Star": _morning_star(c2, c1, c0, downtrend),
        "Bullish Engulfing": _bullish_engulfing(c1, c0, downtrend),
        "Piercing Line": _piercing_line(c1, c0, downtrend),
        "Bullish Harami": _bullish_harami(c1, c0, downtrend),
        "Hammer": _hammer(c0, downtrend),
        "Inverted Hammer": _inverted_hammer(c0, downtrend),
        "Dragonfly Doji": _dragonfly_doji(c0, downtrend),
    }

    for name in PATTERN_PRIORITY:
        if checks[name]:
            return name
    return None


def _hammer(c, downtrend):
    return (
        downtrend
        and c.body <= 0.3 * c.range
        and c.lower_shadow >= 2 * c.body
        and c.upper_shadow <= 0.3 * c.body + 1e-9
    )


def _inverted_hammer(c, downtrend):
    return (
        downtrend
        and c.body <= 0.3 * c.range
        and c.upper_shadow >= 2 * c.body
        and c.lower_shadow <= 0.3 * c.body + 1e-9
    )


def _dragonfly_doji(c, downtrend):
    return (
        downtrend
        and c.body <= 0.05 * c.range
        and c.lower_shadow >= 0.6 * c.range
        and c.upper_shadow <= 0.1 * c.range
    )


def _bullish_engulfing(c1, c0, downtrend):
    return (
        downtrend
        and c1.is_bearish
        and c0.is_bullish
        and c0.open <= c1.close
        and c0.close >= c1.open
        and c0.body > c1.body
    )


def _piercing_line(c1, c0, downtrend):
    return (
        downtrend
        and c1.is_bearish
        and c0.is_bullish
        and c0.open < c1.low
        and c0.close > c1.midpoint
        and c0.close < c1.open
    )


def _bullish_harami(c1, c0, downtrend):
    return (
        downtrend
        and c1.is_bearish
        and c0.is_bullish
        and c0.open >= c1.close
        and c0.close <= c1.open
        and c0.body < c1.body
    )


def _morning_star(c2, c1, c0, downtrend):
    return (
        downtrend
        and c2.is_bearish
        and c2.body >= 0.6 * c2.range
        and c1.body <= 0.3 * c2.body + 1e-9
        and max(c1.open, c1.close) < c2.close
        and c0.is_bullish
        and c0.close > c2.midpoint
    )


def _three_white_soldiers(c2, c1, c0, downtrend):
    candles = [c2, c1, c0]
    if not downtrend:
        return False
    if not all(c.is_bullish for c in candles):
        return False
    if not (c1.close > c2.close and c0.close > c1.close):
        return False
    if not (c1.open > c2.open and c0.open > c1.open):
        return False
    if not all(c.upper_shadow <= 0.25 * c.body + 1e-9 for c in candles):
        return False
    if not all(c.body >= 0.5 * c.range for c in candles):
        return False
    return True
