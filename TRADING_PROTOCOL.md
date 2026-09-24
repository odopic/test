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

## Entry timing and confirmation buffer (changed 2026-09-24)

The owner flagged that entries were too often catching a marginal, barely-green
intraday move that gave most of it back by the actual close (e.g. ROP on
2026-09-23 confirmed at only +0.67% above today's open, then settled the day
only +0.4% up — a weak, unconvincing move that shouldn't have cleared the bar).

Two changes:

1. **Trigger fires 7 minutes before close now, not 15.** Cron moved from
   `45 19 * * 1-5` to `53 19 * * 1-5` (19:53 UTC = 3:53pm ET during EDT).
   Rationale: the three-red-day pattern itself (days 1-3) is fixed, settled
   data and can be scanned any time; only the day-4 confirmation check needs
   to be close to the bell. Checking closer to the close shortens the window
   in which the "confirmed" move can still reverse, without cutting it so
   close (e.g. 20-30 seconds) that a slow API call risks missing the window
   for a market order to complete within regular hours. Like the 19:45
   original schedule, this assumes EDT — shift by an hour around the Nov/Mar
   US DST transitions if not updated by then.
2. **Confirmation buffer raised from 0.1% to 1%** (see
   `three_red_reversal_day4_probable` in `scanner/patterns.py`). A signal now
   needs current price ≥ today's open × 1.01, not × 1.001, before it counts
   as a confirmed bullish day 4. This mechanically requires a much more
   convincing intraday move and should exclude the kind of razor-thin,
   easily-reversed confirmations (WDAY, VRSK, CTSH, ROP on 2026-09-23 were
   all between +0.14% and +1.5% — most would now fail this bar) that were
   producing entries which flipped red by the close.

Net effect: fewer entries per day, but each one should represent real
intraday conviction rather than noise. If this proves too strict (skips
every candidate most days), it can be loosened — but the owner's complaint
was specifically about entries being too easily won, so err strict for now.

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
