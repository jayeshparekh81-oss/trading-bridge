"""CLI entry points for the Strategy Template System.

Currently exposes a single command:

    python -m app.templates.scripts.seed_strategy_templates

which idempotently loads the contents of
``backend/data/strategy_templates_seed.json`` into the
``strategy_templates`` table via
:func:`app.templates.registry.load_from_seed_file`.
"""

from __future__ import annotations
