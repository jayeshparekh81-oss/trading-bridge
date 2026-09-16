"""The backend deploys FIRST. The frontend in production must not break.

C4, 2026-09-16. Backend and frontend ship separately — the backend goes to EC2,
the frontend to Vercel — so for some window the CURRENT production frontend
talks to the NEW backend. Any field it reads that this branch removed or
renamed becomes ``undefined`` in a live customer's browser, on a money page,
with no error anywhere.

So the rule is one-directional and mechanical: every response model the
frontend reads may GAIN fields and may never LOSE one, measured against the
commit prod is actually running (``fffc1bf3``, established by md5 of the
running container's modules, not by assumption).

This is a contract test, not a unit test: it reads the schema source at the
prod commit out of git and compares it with the working tree.
"""

from __future__ import annotations

import re
import subprocess

import pytest

#: The commit the prod backend image was built from. Verified on 2026-09-16 by
#: md5-ing the running container's modules against git — NOT the prod tree's
#: HEAD, which sits on an unrelated local-state branch.
PROD_COMMIT = "fffc1bf3"

#: Every response model a customer-facing page deserialises.
WATCHED: dict[str, tuple[str, ...]] = {
    "strategy_position.py": (
        "StrategyPositionRead",
        "StrategyPositionListResponse",
        "KillSwitchResponse",
    ),
    "strategy_execution.py": (
        "StrategyExecutionRead",
        "StrategyExecutionListResponse",
    ),
}


def _fields(src: str, cls: str) -> set[str]:
    body = re.search(rf"class {cls}\(BaseModel\):(.*?)(?=\nclass |\n__all__|\Z)", src, re.S)
    if body is None:
        return set()
    out: set[str] = set()
    for line in body.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("model_config"):
            continue
        name = re.match(r"^([a-z_][a-z0-9_]*)\s*:", stripped)
        if name:
            out.add(name.group(1))
    return out


def _at_prod(filename: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{PROD_COMMIT}:backend/app/schemas/{filename}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"prod commit {PROD_COMMIT} not available in this checkout")
    return result.stdout


def _here(filename: str) -> str:
    from pathlib import Path

    return (Path(__file__).resolve().parents[1] / "app" / "schemas" / filename).read_text()


@pytest.mark.parametrize(
    ("filename", "cls"),
    [(f, c) for f, classes in WATCHED.items() for c in classes],
)
def test_no_field_the_live_frontend_reads_was_removed(filename: str, cls: str) -> None:
    """🔴 THE ONE-DIRECTIONAL RULE. Gaining a field is safe; losing one is not."""
    prod = _fields(_at_prod(filename), cls)
    branch = _fields(_here(filename), cls)
    assert prod, f"could not parse {cls} at {PROD_COMMIT} — the check would pass vacuously"
    removed = prod - branch
    assert not removed, (
        f"{cls} dropped {sorted(removed)} — the production frontend still reads "
        f"them, and the backend deploys first, so they would read as undefined "
        f"on a live money page"
    )


def test_falsification_twin_the_check_can_actually_fail() -> None:
    """The twin. A parser that returns empty sets would pass every case above.

    This proves the comparison has teeth: a model with a field removed IS
    detected.
    """
    prod_like = (
        "class Thing(BaseModel):\n"
        "    model_config = ConfigDict()\n"
        "    kept: int\n"
        "    dropped: str | None = None\n"
    )
    branch_like = "class Thing(BaseModel):\n    kept: int\n"
    assert _fields(prod_like, "Thing") == {"kept", "dropped"}
    assert _fields(branch_like, "Thing") == {"kept"}
    assert _fields(prod_like, "Thing") - _fields(branch_like, "Thing") == {"dropped"}


def test_the_additions_this_branch_makes_are_present() -> None:
    """Sensitivity in the other direction: the three new position fields exist,
    so a future revert that silently drops them is visible here too."""
    branch = _fields(_here("strategy_position.py"), "StrategyPositionRead")
    for field in ("legs_balanced", "incomplete_reason", "duplicate_exit"):
        assert field in branch, f"{field} is gone from StrategyPositionRead"
