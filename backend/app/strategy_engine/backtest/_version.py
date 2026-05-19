"""Engine version module — single source of truth for backtest engine version.

Bump policy (per docs/BACKTEST_ENGINE_EXTENSION_PLAN.md §Engine-version):
- MAJOR on incompatible changes (output schema changes, semantic logic shifts)
- MINOR on additive features (new indicators, new metrics)
- PATCH on bug fixes that don't change output for existing strategies

Idempotency key includes ``__engine_version__`` — bumps invalidate prior
cache entries automatically because the version string is hashed into the
request fingerprint at :mod:`app.backtest_extension.idempotency`.

The three numeric components MUST stay consistent with the string form;
the consistency invariant is asserted by
``tests/backtest_extension/test_engine_version.py``.
"""

from __future__ import annotations

__engine_version__: str = "v1.0.0"
__engine_version_major__: int = 1
__engine_version_minor__: int = 0
__engine_version_patch__: int = 0

__all__ = [
    "__engine_version__",
    "__engine_version_major__",
    "__engine_version_minor__",
    "__engine_version_patch__",
]
