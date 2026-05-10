"""Minimal Pine source preprocessor — strip comments, normalise whitespace.

Pine's comment syntax:

    Single-line:  ``// comment``
    Block-line:   no native block comments; multi-line strings via "..."
                  inside ``// @description`` blocks are not real comments.

The preprocessor returns the source with comments stripped (so the
parser doesn't have to distinguish `ta.ema` from `// fake call to
ta.ema`) plus a parallel list of stripped comment lines that the
validator may consult for license markers.

This module is **purely textual** — no eval, no exec, no compile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PreprocessedSource:
    """Output of :func:`preprocess`."""

    code: str
    """Source with comments stripped, lines preserved by index."""
    comments: tuple[str, ...]
    """Stripped comment text (the part after ``//`` on each line)."""


_LINE_COMMENT = re.compile(r"//[^\n]*")


def preprocess(source: str) -> PreprocessedSource:
    """Strip ``//`` line comments; collect their text for downstream use.

    String literals containing ``//`` survive — Pine has only one kind
    of string delimiter (``"``), and we treat any ``//`` outside a
    string as a comment opener.
    """
    comments: list[str] = []
    out_lines: list[str] = []
    for line in source.splitlines():
        comment_start = _find_unquoted_double_slash(line)
        if comment_start is None:
            out_lines.append(line)
            continue
        comment_text = line[comment_start + 2 :].strip()
        if comment_text:
            comments.append(comment_text)
        out_lines.append(line[:comment_start].rstrip())
    return PreprocessedSource(
        code="\n".join(out_lines),
        comments=tuple(comments),
    )


def _find_unquoted_double_slash(line: str) -> int | None:
    """Return the column where ``//`` starts a comment, ignoring those
    inside double-quoted strings. ``None`` if the line has no comment."""
    in_string = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"' and (i == 0 or line[i - 1] != "\\"):
            in_string = not in_string
        elif not in_string and ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            return i
        i += 1
    return None


__all__ = ["PreprocessedSource", "preprocess"]
