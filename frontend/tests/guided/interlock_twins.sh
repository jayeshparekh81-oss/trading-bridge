#!/usr/bin/env bash
# Falsification twins for THE SWITCH-ON INTERLOCK (founder 26 Sep). Each twin removes one piece of
# the interlock in a SCRATCH copy of the frontend (never this worktree) and runs
# tests/guided/flag-interlock.test.tsx; every twin must turn it RED. Control = unmodified copy, GREEN.
# Run under the heavy-job lock: flock -n /home/ubuntu/ops/state/heavy_job.lock bash tests/guided/interlock_twins.sh
set -uo pipefail
SRC=$(cd "$(dirname "$0")/../.." && pwd)
SCR=${TWIN_SCRATCH:-/tmp/interlock_twins_$$}
rm -rf "$SCR"; mkdir -p "$SCR"
( cd "$SRC" && tar --exclude=./node_modules --exclude=./.next -cf - . ) | ( cd "$SCR" && tar -xf - )
ln -s "$(readlink -f "$SRC/node_modules")" "$SCR/node_modules"
run() { ( cd "$SCR" && npx vitest run tests/guided/flag-interlock.test.tsx 2>&1 | grep -E "Tests +[0-9]" | tail -1 ); }
mutate() { # file old new
  python3 - "$SCR/$1" "$2" "$3" <<'PY'
import sys
p, old, new = sys.argv[1:4]
s = open(p).read()
assert old in s, f"mutation anchor not found in {p}: {old!r}"
open(p, "w").write(s.replace(old, new, 1))
PY
}
restore() { cp -p "$SRC/$1" "$SCR/$1"; }
echo "CONTROL (unmodified): $(run)"
declare -a T=(
  "T1 hook trusts the frontend flag alone|src/hooks/useGuidedPathLive.ts|return enabled ? answer : \"off\";|return enabled ? \"ready\" : \"off\";"
  "T2 a failed readiness call counts as ready|src/lib/guided-path.ts|.then(isReadyBody, () => false)|.then(isReadyBody, () => true)"
  "T3 a readiness timeout counts as ready|src/lib/guided-path.ts|timer = setTimeout(() => resolve(false), timeoutMs);|timer = setTimeout(() => resolve(true), timeoutMs);"
  "T4 any 200 body counts as ready|src/lib/guided-path.ts|return b.api === \"guided-path\" && b.ready === true;|return true;"
  "T5 the dashboard redirects on the flag, not on readiness|src/app/(dashboard)/layout.tsx|if (guided === \"ready\") {|if (guided !== \"off\") {"
  "T6 /start renders the path on the flag alone|src/app/start/page.tsx|if (live === \"not-ready\") return <NotSwitchedOn testId=\"guided-not-ready\" />;|if (live === \"not-ready\") return <GuidedPath />;"
)
for t in "${T[@]}"; do
  IFS='|' read -r name file old new <<< "$t"
  mutate "$file" "$old" "$new" || { echo "$name: MUTATION NOT APPLIED"; continue; }
  echo "$name: $(run)"
  restore "$file"
done
echo "CONTROL (restored): $(run)"
rm -rf "$SCR"
