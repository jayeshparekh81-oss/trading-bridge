"""Recursive diff between two strategy snapshots.

Compares two ``strategy_json`` dicts field by field and returns a
sorted list of :class:`StrategyVersionDiff` records plus a Hinglish
summary suitable for the Strategy Coach UI.

Field paths use bracket-and-dot notation so a UI can highlight the
exact element that changed:

* ``"stop_loss_percent"`` — top-level key
* ``"indicators[2].period"`` — third indicator's ``period``
* ``"exits[0].rules[1]"`` — second rule of the first exit block

The summary is intentionally generated from the diff list (not the
raw dicts) so adding a new field never silently changes the wording —
it shows up as ``"X added"`` or contributes to the indicator/exit
counters, then any specific stop-loss / target wording is layered on
top.
"""

from __future__ import annotations

from typing import Any

from app.strategy_engine.strategy_versioning.models import (
    ChangeType,
    StrategyVersionDiff,
)

_INDICATORS_KEY = "indicators"
_ENTRY_KEYS = ("entry_conditions", "entries", "entry")
_EXIT_KEYS = ("exit_conditions", "exits", "exit_rules", "exit")
_STOP_LOSS_KEYS = ("stop_loss_percent", "stop_loss", "sl_percent", "sl")
_TARGET_KEYS = ("target_percent", "take_profit_percent", "target", "tp")


def diff_strategy_json(
    old: dict[str, Any],
    new: dict[str, Any],
) -> list[StrategyVersionDiff]:
    """Return the field-level diff between two strategy snapshots.

    The result is deterministic: identical inputs produce identical
    output ordering (lexicographic on ``field_path``). Lists are
    compared positionally — index ``i`` of ``old`` is compared with
    index ``i`` of ``new`` — and length mismatches surface as
    ``"added"`` or ``"removed"`` entries for the trailing positions.

    Args:
        old: The earlier snapshot.
        new: The later snapshot.

    Returns:
        Sorted list of :class:`StrategyVersionDiff` records. Empty
        when the two dicts are structurally equal.
    """
    diffs: list[StrategyVersionDiff] = []
    _walk_dict(old, new, path="", out=diffs)
    diffs.sort(key=lambda d: d.field_path)
    return diffs


def _walk(
    old: Any,
    new: Any,
    *,
    path: str,
    out: list[StrategyVersionDiff],
) -> None:
    """Dispatch comparison on the *type* of the values at ``path``.

    Mixed-type changes (e.g. dict → list) are recorded as a single
    ``"modified"`` diff at ``path`` rather than a deep recursion —
    the entire shape changed, so a UI doesn't gain anything from a
    spray of nested ``"removed"``/``"added"`` entries.
    """
    if isinstance(old, dict) and isinstance(new, dict):
        _walk_dict(old, new, path=path, out=out)
        return
    if isinstance(old, list) and isinstance(new, list):
        _walk_list(old, new, path=path, out=out)
        return
    if old != new:
        out.append(
            StrategyVersionDiff(
                field_path=path or "<root>",
                old_value=old,
                new_value=new,
                change_type="modified",
            )
        )


def _walk_dict(
    old: dict[str, Any],
    new: dict[str, Any],
    *,
    path: str,
    out: list[StrategyVersionDiff],
) -> None:
    for key in sorted(set(old) | set(new)):
        sub_path = f"{path}.{key}" if path else key
        if key not in old:
            out.append(
                _leaf_change(sub_path, change_type="added", new_value=new[key])
            )
        elif key not in new:
            out.append(
                _leaf_change(sub_path, change_type="removed", old_value=old[key])
            )
        else:
            _walk(old[key], new[key], path=sub_path, out=out)


def _walk_list(
    old: list[Any],
    new: list[Any],
    *,
    path: str,
    out: list[StrategyVersionDiff],
) -> None:
    common = min(len(old), len(new))
    for i in range(common):
        _walk(old[i], new[i], path=f"{path}[{i}]", out=out)
    for i in range(common, len(new)):
        out.append(
            _leaf_change(f"{path}[{i}]", change_type="added", new_value=new[i])
        )
    for i in range(common, len(old)):
        out.append(
            _leaf_change(f"{path}[{i}]", change_type="removed", old_value=old[i])
        )


def _leaf_change(
    path: str,
    *,
    change_type: ChangeType,
    old_value: Any = None,
    new_value: Any = None,
) -> StrategyVersionDiff:
    return StrategyVersionDiff(
        field_path=path,
        old_value=old_value,
        new_value=new_value,
        change_type=change_type,
    )


def summarise_hinglish(
    old: dict[str, Any],
    new: dict[str, Any],
    diffs: list[StrategyVersionDiff],
) -> str:
    """Build a beginner-friendly Hinglish summary of the diff.

    The wording is layered:

    1. Indicator add/remove/modify counts (if any).
    2. Specific stop-loss change (``"Stop loss changed from X% to Y%"``).
    3. Specific target change.
    4. Generic "Entry conditions modified" / "Exit conditions modified"
       when those branches changed but no specific wording matched.
    5. Fallback ``"X fields modified"`` when nothing else triggered —
       guarantees a non-empty summary so the comparison model's
       ``min_length=1`` validator never fails.
    """
    parts: list[str] = []

    indicator_summary = _indicator_summary(diffs)
    if indicator_summary:
        parts.append(indicator_summary)

    sl_summary = _scalar_change_summary(old, new, _STOP_LOSS_KEYS, label="Stop loss")
    if sl_summary:
        parts.append(sl_summary)

    target_summary = _scalar_change_summary(old, new, _TARGET_KEYS, label="Target")
    if target_summary:
        parts.append(target_summary)

    if _branch_touched(diffs, _ENTRY_KEYS):
        parts.append("Entry conditions modified")
    if _branch_touched(diffs, _EXIT_KEYS):
        parts.append("Exit conditions modified")

    if not parts:
        if not diffs:
            return "No changes between versions"
        parts.append(f"{len(diffs)} field(s) modified")

    return ". ".join(parts) + "."


def _indicator_summary(diffs: list[StrategyVersionDiff]) -> str:
    added = removed = modified = 0
    for d in diffs:
        if not d.field_path.startswith(_INDICATORS_KEY):
            continue
        # Only count the *outermost* change per indicator slot. A
        # nested edit like ``indicators[2].period`` counts as one
        # ``modified`` indicator regardless of how many leaves moved.
        if _is_top_level_indicator_path(d.field_path):
            if d.change_type == "added":
                added += 1
            elif d.change_type == "removed":
                removed += 1
            else:
                modified += 1
        else:
            # Nested change inside an existing indicator — credit it
            # once via a ``modified`` bump, but only the first time
            # we see this slot. We approximate by counting the
            # ``indicators[N]`` prefix uniquely.
            pass
    # Second pass: count distinct nested-modified slots that didn't
    # already register as a top-level change.
    seen_nested: set[str] = set()
    top_level_seen: set[str] = set()
    for d in diffs:
        if not d.field_path.startswith(_INDICATORS_KEY):
            continue
        slot = _indicator_slot_prefix(d.field_path)
        if slot is None:
            continue
        if _is_top_level_indicator_path(d.field_path):
            top_level_seen.add(slot)
        else:
            seen_nested.add(slot)
    nested_only = seen_nested - top_level_seen
    modified += len(nested_only)

    pieces: list[str] = []
    if added:
        pieces.append(f"{added} indicator{'s' if added != 1 else ''} added")
    if removed:
        pieces.append(f"{removed} indicator{'s' if removed != 1 else ''} removed")
    if modified:
        pieces.append(f"{modified} indicator{'s' if modified != 1 else ''} modified")
    return ", ".join(pieces)


def _is_top_level_indicator_path(path: str) -> bool:
    """``True`` when ``path`` points at a whole indicator slot
    (``"indicators[3]"``) rather than a field inside one."""
    if not path.startswith(_INDICATORS_KEY + "["):
        return False
    closing = path.find("]")
    if closing == -1:
        return False
    return closing == len(path) - 1


def _indicator_slot_prefix(path: str) -> str | None:
    """Return ``"indicators[N]"`` for a path inside the indicators
    list, else ``None``."""
    if not path.startswith(_INDICATORS_KEY + "["):
        return None
    closing = path.find("]")
    if closing == -1:
        return None
    return path[: closing + 1]


def _branch_touched(diffs: list[StrategyVersionDiff], keys: tuple[str, ...]) -> bool:
    for d in diffs:
        for key in keys:
            if d.field_path == key or d.field_path.startswith(key + ".") or d.field_path.startswith(key + "["):
                return True
    return False


def _scalar_change_summary(
    old: dict[str, Any],
    new: dict[str, Any],
    keys: tuple[str, ...],
    *,
    label: str,
) -> str | None:
    for key in keys:
        if key in old and key in new and old[key] != new[key]:
            return f"{label} changed from {_format_value(old[key])} to {_format_value(new[key])}"
        if key in old and key not in new:
            return f"{label} removed (was {_format_value(old[key])})"
        if key not in old and key in new:
            return f"{label} set to {_format_value(new[key])}"
    return None


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        # Avoid showing 1.5000000001 — round to 4 decimals for display.
        return f"{value:g}"
    return str(value)


__all__ = [
    "diff_strategy_json",
    "summarise_hinglish",
]
