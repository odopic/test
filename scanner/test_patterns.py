"""Lightweight sanity checks for pattern detection (no pytest dependency)."""

from scanner.patterns import detect, detect_morning_star, detect_three_red_then_green, detect_three_red_setup


class Row(dict):
    def __init__(self, o, h, l, c):
        super().__init__(open=o, high=h, low=l, close=c)


class Frame:
    def __init__(self, rows):
        self._rows = rows

    def __len__(self):
        return len(self._rows)

    def __getitem__(self, key):
        if key == "close":
            return [r["close"] for r in self._rows]
        raise KeyError(key)

    class _ILoc:
        def __init__(self, rows):
            self._rows = rows

        def __getitem__(self, idx):
            r = self._rows[idx]
            obj = type("R", (), r)()
            return obj

    @property
    def iloc(self):
        return Frame._ILoc(self._rows)


def downtrend_prefix(start, days, step=-1.0):
    rows = []
    price = start
    for _ in range(days):
        o = price
        c = price + step
        h = max(o, c) + 0.1
        l = min(o, c) - 0.1
        rows.append(Row(o, h, l, c))
        price = c
    return rows, price


def test_hammer():
    prefix, last_close = downtrend_prefix(100, 7)
    hammer = Row(o=last_close - 0.1, h=last_close + 0.02, l=last_close - 3.1, c=last_close)
    rows = prefix + [hammer]
    assert detect(Frame(rows)) == "Hammer", detect(Frame(rows))


def test_bullish_engulfing():
    prefix, last_close = downtrend_prefix(100, 6)
    bear = Row(o=last_close, h=last_close + 0.1, l=last_close - 1.2, c=last_close - 1.0)
    bull = Row(o=bear.get("close") - 0.2, h=bear["open"] + 0.3, l=bear["close"] - 0.3,
               c=bear["open"] + 0.2)
    rows = prefix + [bear, bull]
    result = detect(Frame(rows))
    assert result == "Bullish Engulfing", result


def test_no_pattern_in_uptrend():
    rows = []
    price = 100
    for _ in range(8):
        o = price
        c = price + 1.0
        rows.append(Row(o, c + 0.1, o - 0.1, c))
        price = c
    assert detect(Frame(rows)) is None


def test_three_white_soldiers():
    prefix, last_close = downtrend_prefix(100, 5)
    price = last_close
    soldiers = []
    for _ in range(3):
        o = price + 0.1
        c = o + 2.0
        soldiers.append(Row(o, c + 0.05, o - 0.05, c))
        price = c
    rows = prefix + soldiers
    result = detect(Frame(rows))
    assert result == "Three White Soldiers", result


def test_detect_morning_star():
    prefix, last_close = downtrend_prefix(100, 5)
    day1 = Row(o=last_close, h=last_close + 0.1, l=last_close - 6.0, c=last_close - 5.8)  # tall bearish
    day2 = Row(o=day1["close"] - 0.3, h=day1["close"] + 0.2, l=day1["close"] - 0.6,
               c=day1["close"] - 0.2)  # small indecision body, gapped below day1 close
    day1_mid = (day1["open"] + day1["close"]) / 2
    day3 = Row(o=day2["close"] + 0.2, h=day1_mid + 3.0, l=day2["close"] - 0.1,
               c=day1_mid + 2.5)  # tall bullish, closes well above day1 midpoint
    rows = prefix + [day1, day2, day3]

    result = detect_morning_star(Frame(rows))
    assert result is not None, "expected a confirmed Morning Star"
    assert result["pattern"] == "Morning Star"
    expected_low = min(day1["low"], day2["low"], day3["low"])
    assert result["pattern_low"] == expected_low, (result["pattern_low"], expected_low)

    # detect() (the general multi-pattern scan) should agree it's a Morning Star
    assert detect(Frame(rows)) == "Morning Star"


def test_detect_morning_star_rejects_without_downtrend():
    rows = []
    price = 100
    for _ in range(8):
        o = price
        c = price + 1.0
        rows.append(Row(o, c + 0.1, o - 0.1, c))
        price = c
    assert detect_morning_star(Frame(rows)) is None


def test_three_red_then_green():
    rows = [
        Row(o=100, h=100.2, l=94, c=95),   # day1: red
        Row(o=94.5, h=95, l=89, c=90),     # day2: red, lower close
        Row(o=89.5, h=90, l=84, c=85),     # day3: red, lower close
        Row(o=85.2, h=90, l=85.0, c=89),   # day4: green
    ]
    result = detect_three_red_then_green(Frame(rows))
    assert result is not None
    assert result["pattern"] == "Three Red Days Reversal"
    assert result["pattern_low"] == 84, result["pattern_low"]

    setup = detect_three_red_setup(Frame(rows[:3]))
    assert setup is not None


def test_three_red_then_green_rejects_non_declining_reds():
    rows = [
        Row(o=90, h=90.2, l=84, c=85),     # day1: red
        Row(o=96, h=97, l=93, c=94.5),     # day2: red but close HIGHER than day1 (not declining)
        Row(o=94, h=95, l=89, c=90),       # day3: red
        Row(o=90.2, h=94, l=90.0, c=93),   # day4: green
    ]
    assert detect_three_red_then_green(Frame(rows)) is None


def test_three_red_then_green_rejects_fourth_day_red():
    rows = [
        Row(o=100, h=100.2, l=94, c=95),
        Row(o=94.5, h=95, l=89, c=90),
        Row(o=89.5, h=90, l=84, c=85),
        Row(o=85, h=86, l=82, c=83),       # day4: still red
    ]
    assert detect_three_red_then_green(Frame(rows)) is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    if failed:
        raise SystemExit(f"{failed}/{len(tests)} tests failed")
    print(f"All {len(tests)} tests passed")
