"""Strategy Template System — Phase 1 module.

Houses the strategy-template catalog: 15 active equity templates with
full ``config_json``, 35 cataloged-but-inactive equity entries, and
63 options entries that require the (still-to-be-built) options
strategy builder.

This module is intentionally distinct from the sibling
:mod:`app.templates.notifications` subtree (which holds plain-text and
HTML notification message templates) — only the name space is
shared. The notification templates are static-file assets; this
module is Python code.
"""

from __future__ import annotations
