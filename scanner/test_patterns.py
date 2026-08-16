"""Lightweight sanity checks for pattern detection (no pytest dependency)."""

from scanner.patterns import detect


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
