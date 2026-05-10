"""Pine source-code importer — basic safe subset.

Converts a TradingView Pine v5/v6 script (as a *string*) into a
Tradetri :class:`~app.strategy_engine.schema.strategy.StrategyJSON`
dict. The importer is **static**: there is no execution path of any
kind — the source code is scanned, regex-matched, and structurally
mapped. ``eval``, ``exec``, ``compile``, ``subprocess``, dynamic
``__import__`` are not used; ``test_no_dynamic_code_execution``
asserts this by inspecting this package's source tree.

This module is **distinct** from :mod:`app.services.pine_mapper`,
which translates *live signal payloads* coming off a TradingView
webhook. That module deals with runtime data; this one deals with
source code, and they share no code path.

Public entrypoint: :func:`convert_pine_to_strategy`.
"""

from __future__ import annotations

from app.strategy_engine.pine_import.converter import convert_pine_to_strategy
from app.strategy_engine.pine_import.validator import (
    LicenseStatus,
    ValidationReport,
    validate_source,
)

__all__ = [
    "LicenseStatus",
    "ValidationReport",
    "convert_pine_to_strategy",
    "validate_source",
]
