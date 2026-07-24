# D3 — OPTION EXECUTION EXAM (signals re-priced on RECORDED option premiums)
DESIGN-ONLY DRAFT — pre-Market-DNA. Zero outcome numbers. Depends on D4 (IV-rank).

## Question
When the (separately pre-registered) futures-side signals are EXECUTED as buy-only
CE/PE on the RECORDED ATM±20 premium streams (chains recorded since 07-13), are they
options-viable, or theta/spread-eaten? This is an EXECUTION exam — the signal is held
fixed; only the instrument priced changes.

## Mechanics
- Entry: at signal bar close, buy the selected option at its recorded ask-side price
  (5-level book is recorded for options; use best-ask, slippage per cost model).
- Exit: mirror the signal's exit events in time (stop/target/partial/sleeper/EOD map
  to option exit at recorded bid-side), cost model = OPTION-specific frozen schedule (premium-based brokerage, STT on
  sell-side premium, exchange/SEBI charges on premium, stamp; spread already
  realized via ask-entry/bid-exit). signals/costs.py is futures-only and may NOT
  be reused. FROZEN SCHEDULE PARAMETERS (with this design): brokerage flat/order
  (Dhan Rs.20/executed order per leg); STT 0.15% of SELL-side premium (Budget 2026, effective 01-Apr-2026; the 0.125%
  figure was the old EXERCISE rate — buy-only intraday never exercises); exchange
  txn charge 0.03503% of premium (NSE options); SEBI Rs.10/crore; stamp 0.003%
  buy-side; GST 18% on (brokerage + exchange + SEBI); fills at recorded best-ask
  (entry) / best-bid (exit) — no additional spread term; statutory rates re-pinned
  at Round-2 pre-registration date.
- TWO pre-registered strike variants, BOTH frozen before any result:
  (a) ATM baseline — nearest ATM strike of the signal side (CE long / PE short).
  (b) "VALUE-CHEAP" selector — frozen composite: LOW IV-rank (per D4) + flow-anomaly
      (strike with max |dOI_w2| among ATM±20 on the signal side) + max R:R (premium
      vs the signal's futures-R mapped through recorded delta). NAMED TRAP: Rs-cheap
      != value-cheap — a 3-rupee far-OTM lottery premium is EXPENSIVE in IV/odds
      terms; the selector must rank by the frozen composite, never by raw premium.

## Parameters-to-freeze (before ANY result)
Strike-window (ATM±20 as recorded), the value-cheap composite's three components and
their combination order (propose: filter IV-rank lowest tercile → among those, max
|dOI_w2| → tie-break max R:R), bid/ask fill convention, cost-model version, exit
mapping table, and WHICH signal set is priced (must itself be pre-registered).

## Ledger binding-format entry
- id: R2-17 (new; supersedes the loose R2-11 "IV-aware strike selection" execution idea)
- observation: every exam so far prices futures; the live intent is options; recorded
  ATM±20 premium + book streams exist since 07-13 and are unexamined for execution.
- mechanical rule: re-price frozen signals via the mechanics above, variants (a)/(b).
- parameters-to-freeze: as listed.
- exam design: Round-2 fresh blind data; per-instrument; report gross AND net under
  the full option cost model; variant (b) vs (a) vs futures-priced baseline; DSR
  pays the 2-variant trial count; random-removal null on any subsetting step.
- what-would-kill-it: both variants theta/spread-eaten while futures-priced baseline
  is not (execution-layer verdict: options non-viable at this cadence); or variant
  (b) indistinguishable from (a) (selector adds nothing).

## Dependency
Variant (b) is BLOCKED until D4's IV-rank definition is frozen and its calibration
caveat resolved-or-accepted.
