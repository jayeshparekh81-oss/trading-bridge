# Queue XX Sprint 5c — trin_proxy Investigation Report

**Branch:** `fix/sprint-5c-trin-proxy`
**Time used:** ~15 min of 60 min cap.
**Scope:** Investigate Sprint 4b's all-NaN flag on `trin_proxy`. Identify
root cause; apply mechanical fix only. ZERO indicator math touched.

## 1. Root cause — framework data routing, not indicator math

`trin_proxy` is a **single-symbol TRIN proxy**. Per its docstring:

```
TRIN = (advancing issues / declining issues) /
       (advancing volume / declining volume)

Single-symbol proxy substitutes "advancing issues" with bullish bars
(close >= open) and "advancing volume" with the volume on those bars,
computed over a trailing window.

Edge cases:
  * Window with zero bear count or bear volume -> None
```

The indicator **correctly returns None** when the input window has no
volume on bearish bars (`bear_vol == 0`). This is documented edge-case
behaviour, not a bug.

**Why Sprint 4b saw all-NaN:** the framework routed `trin_proxy` to the
NIFTY ^NSEI 5m dataset, which carries **zero volume on every bar**
(NIFTY is an index, not a tradable instrument). With every bar's
volume = 0, `bull_vol = bear_vol = 0` on every window → `bear_vol == 0`
→ output is None on every bar.

The framework's `is_volume_aware()` regex in
`backend/tests/queue_xx_sprint_3/framework_extensions/references.py`
matches patterns like `mfi`, `obv`, `vwap`, `cmf`, etc. — but does not
match `trin`. So the framework routed `trin_proxy` to NIFTY (the
non-volume default) instead of RELIANCE.NS.

## 2. Verification on volume-bearing data

Re-ran `trin_proxy` on RELIANCE.NS 5m (4291 bars):

| Dataset | Volume range | finite output | NaN output |
|---|---|---:|---:|
| NIFTY ^NSEI 5m | [0, 0] | 0 / 4280 | **4280 / 4280** |
| **RELIANCE.NS 5m** | **[0, 9.8M]** | **4269 / 4291** | 22 / 4291 (warmup) |

On RELIANCE the finite values fall in the expected TRIN range
`[0.14, 16.2]` with mean 1.17 — consistent with TRIN's centred-at-1
behaviour (values > 1 = bearish, < 1 = bullish on the trailing window).

## 3. Hand-roll cross-check — bit-exact Tier A

Wrote a hand-roll matching the docstring formula verbatim and compared
against TRADETRI on RELIANCE.NS:

| Test | max abs Δ | Result |
|---|---:|---|
| TRADETRI `trin_proxy` vs hand-roll | **0.0000e+00** | bit-exact |

**`trin_proxy` is Tier A.**

## 4. Mechanical fix recommendation

**Add `"trin"` to the volume-aware pattern list in
`framework_extensions/references.py:VOLUME_AWARE_PATTERNS`.**

Single-line addition; framework_extensions are non-production test
infrastructure. The fix is required for any future verification sweep
to route `trin_proxy` to volume-bearing data.

Sprint 5b already applied this fix inline in
`sprint_5b_handrolls.py:is_vol_aware()`. **Sprint 5d framework v2 will
formalize this in the consolidated module.** No Sprint 5c-only code
change needed beyond this documentation.

## 5. Tier scoreboard delta from Sprint 5c

| Before Sprint 5c | After Sprint 5c |
|---|---|
| 53 A | **54 A** (+trin_proxy) |
| 14 B | 14 B (unchanged) |
| 0 C | 0 C |
| 2 D | 2 D (consecutive_higher_lows + VWAP — unchanged) |
| 80 cumulative | **81 cumulative** |

trin_proxy moves from NEEDS_MANUAL_REVIEW (4b math flag) to Tier A
verified.

## 6. Sprint 5c hard-stops — all clear

| # | Cap | Observed | Status |
|---:|---|---|:---:|
| 1 | Sub-sprint time ≤ 60 min | 15 min | ✓ |
| 4 | Math fix attempted | 0 | ✓ |
| 5 | Math fix beyond mechanical | 0 (data routing only) | ✓ |
| 6 | Main merge attempted | 0 | ✓ |

## 7. Sprint 5c artifacts

- `docs/QUEUE_XX_SPRINT_5C_REPORT.md` (this file)
- No new code files — fix is a single-line addition to a Sprint 3 file
  that lives on a different branch, formalized in Sprint 5d.

## 8. Sprint 5c lesson (lesson #11 for the chain)

**"All-NaN" output from a volume-aware indicator usually means
volume-data routing failed, not a math bug.** Pattern: before flagging
a math bug, verify the indicator runs cleanly on a volume-bearing
dataset (RELIANCE.NS or equivalent). Sprint 4b's flag was correctly
flagged-for-review (not auto-fixed), and Sprint 5c was the right
follow-up — but the underlying issue is mundane.

For Sprint 5d's framework v2: extend `is_volume_aware()` to be
explicit (whitelist by name) rather than pattern-matching, so this
class of false alarm doesn't recur.
