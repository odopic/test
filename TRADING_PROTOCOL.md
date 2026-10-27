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

## Allocation per position: $1,000 (changed 2026-10-26)

`ALLOCATION_PER_POSITION` in `scanner/strategy.py` is now **1000.0** (was
500.0). The owner added $3,000 in fresh capital to the account on this date.
Every new entry from here on sizes against the $1,000 cap via
`build_three_red_reversal_signal`; existing open positions are not
retroactively resized.

## Fully deploying small leftover cash (changed 2026-10-26)

Whole-share sizing (`floor(allocation / entry_price)`) always leaves a few
dollars of unspent cash behind, since share prices rarely divide evenly into
the allocation. Over time this leftover accumulates into a "stuck" cash
balance too small to comfortably size a normal position, especially now
that $1,000 is the per-position cap.

Rule: when the account's buying power (via `get_portfolio`) is **under
$300** at the moment of sizing a confirmed signal, do not floor-divide into
whole shares. Instead place the buy as a `market` order with `dollar_amount`
set to the full available buying power (Robinhood computes fractional
shares automatically) — regular trading hours only, per
`place_equity_order`'s fractional-share rules. This spends the cash down to
$0 rather than leaving a remainder on the sidelines. Record the resulting
`entry_price` as the fill's `average_price` and size `shares` from the
fill's `cumulative_quantity` (which may be fractional) when updating
`portfolio_state.json`.

Above the $300 threshold, continue sizing whole shares against the $1,000
allocation cap as before.

## Entry scan running past the close (discovered 2026-10-27)

On 2026-10-27 the universe entry scan (quotes + historicals across ~89
tickers, batched at 10 symbols/call) took long enough in wall-clock time
that by the time a candidate's day-4 confirmation was checked, regular
trading hours had already ended (`get_equity_quotes` showed
`last_non_reg_trade_price` with a timestamp after `last_trade_price`,
i.e. after-hours trading had already started). GOOGL cleared the 1%
confirmation buffer (+1.12% above today's open) but the signal was
discovered too late to act on with a same-day market order — a market
order placed after the close queues for the next regular open instead of
filling near the confirmed level, which reintroduces the overnight-gap
risk this strategy's near-close timing was specifically designed to
avoid (see "Entry timing and confirmation buffer" above).

Rule: before placing an entry order, check whether regular hours are
still open (a quote with a `last_non_reg_trade_price` timestamp newer
than `last_trade_price` means they are not). If hours have already
closed, do NOT place the market buy — record the ticker as "confirmed
but not executed (scan completed after close)" in the report and let it
re-qualify from a fresh day-4 check next session. Do not chase it with an
extended-hours limit order; that changes the execution characteristics
(wider spreads, thinner liquidity) the strategy wasn't designed around.
If this keeps happening, the fix is to shrink/parallelize the scan or
move the trigger earlier, not to improvise an after-hours order.

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
