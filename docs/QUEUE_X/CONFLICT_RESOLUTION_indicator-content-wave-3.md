# Queue X — Phase C2: feat/indicator-content-wave-3

**Status:** CONFLICT (union-mergeable in registry.ts only)
**Branch:** 22 ahead / 92 behind main
**Risk:** LOW — additive only

## Anatomy of the conflict
The branch adds 22 files (20 content/*.ts + 1 test + 1 registry.ts edit), totaling +1,835 lines.

- **All 20 new `content/*.ts` files are net-new** — verified: each path absent on main → no file-level collisions, git merge accepts them automatically.
- **The only conflict is `registry.ts`** — both main and the branch independently grew it after merge-base `f2911509`:
  - Main added wave-2 indicators (ALMA, AWESOME_OSCILLATOR, BALANCE_OF_POWER, CHANDE_MOMENTUM_OSCILLATOR, CHOPPINESS_INDEX, DMI_PLUS/MINUS, DEMA, EOM, FISHER_TRANSFORM, FORCE_INDEX, HMA, KAMA, LINEAR_REGRESSION, NEGATIVE_/POSITIVE_VOLUME_INDEX, TEMA, TRIX, ULTIMATE_OSCILLATOR, ZLEMA — ~20 entries).
  - Wave-3 adds: MASS_INDEX, COPPOCK_CURVE, DETRENDED_PRICE_OSCILLATOR, PRICE_OSCILLATOR, ACCELERATOR_OSCILLATOR, WILLIAMS_VIX_FIX, RELATIVE_VIGOR_INDEX, DEMARKER, ACCUMULATION_DISTRIBUTION, PRICE_VOLUME_TREND, KLINGER_OSCILLATOR, ELDER_RAY_BULL_BEAR, SCHAFF_TREND_CYCLE, RANDOM_WALK_INDEX, LINEAR_REGRESSION_CHANNEL, STANDARD_ERROR_CHANNEL, MCGINLEY_DYNAMIC, SWING_INDEX, ACCUMULATIVE_SWING_INDEX, COMPARATIVE_RELATIVE_STRENGTH (20 entries).
- Zero overlap between the two added-entry sets.

Resolution policy: **keep ALL imports + ALL INDICATORS entries from BOTH sides**.

## Recommendation
**Rebase wave-3 onto main, hand-resolve registry.ts as union**, then merge.

The non-registry conflict surface is zero (file-level adds only). The registry.ts merge is mechanical.

## Paste-able commands (tomorrow evening)

```bash
# 1. Set up rebase
git fetch origin
git checkout -b merge/indicator-content-wave-3 origin/feat/indicator-content-wave-3
git rebase origin/main
# Expected single conflict: frontend/src/lib/indicators/registry.ts
```

When the rebase pauses on registry.ts:

```bash
# 2. Take main's version as the base (it already has wave-2)
git checkout --theirs frontend/src/lib/indicators/registry.ts
# Open it in editor and append wave-3 imports + entries from the conflict markers.
# OR use the scripted append below.
```

### Scripted union merge of registry.ts

```bash
# After taking main's version, append wave-3's 20 imports and 20 entries
cat <<'IMPORTS_PATCH' > /tmp/wave3_imports.txt
import { MASS_INDEX } from "./content/mass-index";
import { COPPOCK_CURVE } from "./content/coppock-curve";
import { DETRENDED_PRICE_OSCILLATOR } from "./content/detrended-price-oscillator";
import { PRICE_OSCILLATOR } from "./content/price-oscillator";
import { ACCELERATOR_OSCILLATOR } from "./content/accelerator-oscillator";
import { WILLIAMS_VIX_FIX } from "./content/williams-vix-fix";
import { RELATIVE_VIGOR_INDEX } from "./content/relative-vigor-index";
import { DEMARKER } from "./content/demarker";
import { ACCUMULATION_DISTRIBUTION } from "./content/accumulation-distribution";
import { PRICE_VOLUME_TREND } from "./content/price-volume-trend";
import { KLINGER_OSCILLATOR } from "./content/klinger-oscillator";
import { ELDER_RAY_BULL_BEAR } from "./content/elder-ray-bull-bear";
import { SCHAFF_TREND_CYCLE } from "./content/schaff-trend-cycle";
import { RANDOM_WALK_INDEX } from "./content/random-walk-index";
import { LINEAR_REGRESSION_CHANNEL } from "./content/linear-regression-channel";
import { STANDARD_ERROR_CHANNEL } from "./content/standard-error-channel";
import { MCGINLEY_DYNAMIC } from "./content/mcginley-dynamic";
import { SWING_INDEX } from "./content/swing-index";
import { ACCUMULATIVE_SWING_INDEX } from "./content/accumulative-swing-index";
import { COMPARATIVE_RELATIVE_STRENGTH } from "./content/comparative-relative-strength";
IMPORTS_PATCH

cat <<'ENTRIES_PATCH' > /tmp/wave3_entries.txt
  "mass-index": MASS_INDEX,
  "coppock-curve": COPPOCK_CURVE,
  "detrended-price-oscillator": DETRENDED_PRICE_OSCILLATOR,
  "price-oscillator": PRICE_OSCILLATOR,
  "accelerator-oscillator": ACCELERATOR_OSCILLATOR,
  "williams-vix-fix": WILLIAMS_VIX_FIX,
  "relative-vigor-index": RELATIVE_VIGOR_INDEX,
  "demarker": DEMARKER,
  "accumulation-distribution": ACCUMULATION_DISTRIBUTION,
  "price-volume-trend": PRICE_VOLUME_TREND,
  "klinger-oscillator": KLINGER_OSCILLATOR,
  "elder-ray-bull-bear": ELDER_RAY_BULL_BEAR,
  "schaff-trend-cycle": SCHAFF_TREND_CYCLE,
  "random-walk-index": RANDOM_WALK_INDEX,
  "linear-regression-channel": LINEAR_REGRESSION_CHANNEL,
  "standard-error-channel": STANDARD_ERROR_CHANNEL,
  "mcginley-dynamic": MCGINLEY_DYNAMIC,
  "swing-index": SWING_INDEX,
  "accumulative-swing-index": ACCUMULATIVE_SWING_INDEX,
  "comparative-relative-strength": COMPARATIVE_RELATIVE_STRENGTH,
ENTRIES_PATCH

# Hand-merge in editor:
#  - Paste /tmp/wave3_imports.txt into the import block (after the existing imports).
#  - Paste /tmp/wave3_entries.txt into INDICATORS = { ... }, before the closing `};`.

git add frontend/src/lib/indicators/registry.ts
git rebase --continue
```

### Verify and push

```bash
# Type-check + tests
cd frontend && pnpm test -- indicators/wave-3-registry.test.ts indicators/registry.test.ts
pnpm tsc --noEmit

# If green, fast-forward and clean up
git checkout main && git merge --ff-only merge/indicator-content-wave-3
git push origin main
git push origin --delete feat/indicator-content-wave-3
```

## Notes
- `INDICATOR_COUNT` is derived (`Object.keys(INDICATORS).length`), so it auto-updates — no manual count edit needed.
- Insertion order is internal; UI sorts alphabetically. Order of appended entries does not affect rendering.
- The branch also adds `frontend/tests/indicators/wave-3-registry.test.ts` with 105 lines of coverage — non-conflicting.

Estimated time: 12 min including type-check.
