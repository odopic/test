# Live order protocol (supersedes the daily trigger's boilerplate exit steps)

As of 2026-09-21, exits are no longer decided by a once-a-day price check.

## Standing stop-loss orders

Every open position has a real **`stop_market`, `time_in_force=gtc`** sell order
resting on the exchange at its `stop_loss` price (see `stop_order_id` in
`portfolio_state.json`). This fires any time the market is open, not just in the
pre-close window, so a position can no longer blow through its stop unnoticed
between daily cycles.

RobinHood's OCO/bracket order type (`place_advanced_order`) is NOT enabled on
this account (`SERVICE_DISABLED`), so there is no single order that also carries
the take-profit leg. **Target hits are still checked and executed manually**
during the daily cycle (compare current price to `target_price`; if hit, cancel
that position's standing stop order via `cancel_advanced_order`/order-cancel,
then market SELL). Missing a target for a few hours is a much smaller risk than
missing a stop-loss, which is why only the stop got a standing order.

## Take-profit target: +20% (changed 2026-09-21)

`TAKE_PROFIT_MULTIPLIER` in `scanner/strategy.py` is now **1.20** (was 1.10).
Rationale: now that the stop trails up daily, the position is protected against
giving back gains, so the target can be set further out to let winners run
further before taking profit. All 9 positions open at the time of the change
had their `target_price` recomputed to entry_price × 1.20. Every new entry from
here on uses the 1.20 multiplier automatically via `build_three_red_reversal_signal`.

Robinhood rejects stop prices with more than 2 decimal places on symbols above
$1 ("subpenny increments"). Round to the nearest cent when placing/replacing.

## Trailing the stop (ratchets up only, once per day)

There is no native trailing-stop order type available here, so the trail is
simulated once per daily cycle:

1. Pull yesterday's and the day-before's completed daily bars (close + high) for
   each open position.
2. If yesterday's close OR high exceeds the prior day's close OR high (i.e. the
   stock made a new high), the new stop level = yesterday's **low**.
3. Only ratchet **up** — never lower an existing stop.
4. If the new level is higher than the current `stop_loss`: cancel the existing
   standing stop order, then **before placing the new one, check the new level
   against the current live price**:
   - If current price is still above the new level: place the new
     `stop_market`/`gtc` order normally, update `stop_loss` and
     `stop_order_id` in `portfolio_state.json`.
   - If current price has already fallen to/through the new level (discovered
     2026-09-23, e.g. PDD/PEP): do NOT place a stop order — Robinhood rejects a
     stop whose trigger is already breached, leaving the position with **no
     protective order at all** until the rejection is noticed. Instead, treat
     it as an immediate stop-loss: market SELL right away (this is also the
     economically correct behavior — the position failed to hold above the
     prior day's low), then record `exit_reason: "stop_loss"` and move it to
     `closed_positions`.

## Daily cycle changes

- Do NOT manually market-sell on a stop breach anymore — the standing order
  handles it. Instead, check `get_equity_orders` for the standing stop orders;
  any that show `state: filled` are exits that already happened. Move that
  position to `closed_positions` (`exit_reason: "stop_loss"`) using the fill's
  `average_price`, then note it happened intraday (not necessarily near close).
- Still check `target_price` manually and market-sell + cancel the stop order
  if hit (`exit_reason: "target"`).
- Run the trailing-stop update (above) for every remaining open position.
- New entries: after a buy fills, immediately place its standing GTC stop_market
  sell order and record `stop_order_id` before moving on.
