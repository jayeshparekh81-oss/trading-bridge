"""Demonstrates the quarantine guard firing (no S3 access: check() runs before any read)."""
import sys, json
from pathlib import Path
D3 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D3)); import qguard as Q
q = json.loads((D3 / "QUARANTINE.json").read_text()); conf, disc = q["confirmation"], q["discovery"]
fired = 0
for stage in ("CP1", "CP2", "CP4", "CP5"):
    try: Q.check(conf[0], stage); print(f"  {stage} requesting confirmation date {conf[0]}: NOT BLOCKED (BUG)")
    except Q.QuarantineError as e: fired += 1; print(f"  {stage} requesting confirmation date {conf[0]}: RAISED QuarantineError -> {e}")
try: Q.check(conf[-1], "CP6"); print(f"  CP6 requesting confirmation date {conf[-1]}: allowed (as designed)")
except Q.QuarantineError as e: print(f"  CP6 blocked (BUG): {e}")
try: Q.check(disc[0], "CP4"); print(f"  CP4 requesting discovery date {disc[0]}: allowed (as designed)")
except Q.QuarantineError as e: print(f"  CP4 discovery blocked (BUG): {e}")
print(f"  guard fired {fired}/4 times for pre-CP6 stages; denied attempts logged: {sum(1 for r in Q.access_log() if not r.get('allowed'))}")
