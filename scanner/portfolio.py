"""JSON-backed open-position store for the scanner strategy."""

import json
import os

from . import strategy

DEFAULT_STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "portfolio_state.json")


def load(path=DEFAULT_STATE_PATH):
    if not os.path.exists(path):
        return {"open_positions": [], "closed_positions": []}
    with open(path) as f:
        return json.load(f)


def save(state, path=DEFAULT_STATE_PATH):
    with open(path, "w") as f:
        json.dump(state, f, indent=2, default=str)


def is_held(state, ticker):
    return any(p["ticker"] == ticker for p in state["open_positions"])


def open_position(state, signal, entry_date):
    position = dict(signal)
    position["entry_date"] = str(entry_date)
    state["open_positions"].append(position)
    return position


def evaluate_all(state, current_prices):
    """current_prices: {ticker: price}. Moves stopped-out / target-hit
    positions from open_positions to closed_positions in place. Returns a
    list of monitoring rows for the report."""
    rows = []
    still_open = []
    for pos in state["open_positions"]:
        price = current_prices.get(pos["ticker"])
        if price is None:
            rows.append({**pos, "current_price": None, "action": "DATA_MISSING",
                         "unrealized_pct": None})
            still_open.append(pos)
            continue

        action = strategy.evaluate_exit(pos, price)
        pnl = strategy.unrealized_pct(pos, price)
        rows.append({**pos, "current_price": round(price, 2), "action": action,
                     "unrealized_pct": pnl})

        if action == "HOLD":
            still_open.append(pos)
        else:
            closed = dict(pos)
            closed["exit_price"] = round(price, 2)
            closed["exit_reason"] = action
            closed["unrealized_pct"] = pnl
            state["closed_positions"].append(closed)

    state["open_positions"] = still_open
    return rows
