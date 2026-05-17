"""Fixtures for Week-2 backtest extension tests.

Contents:

    sample_enqueue_request.json
        Minimal BacktestEnqueueRequest payload (anonymous-config preview).
        Used by Day 2 idempotency tests + Day 4 API contract tests.

    sample_strategy_config.json
        A Phase-1 active template's config_json verbatim, suitable for
        plugging into ``BacktestEnqueueRequest.strategy_config``.

    expected_request_hash.txt
        Pinned SHA-256 hex output of compute_request_hash(...) on
        sample_enqueue_request.json. Day 2 tests assert this exact value
        — drift means either:
        (a) the canonicalisation broke, or
        (b) engine_version bumped (intentional cache-bust).

    determinism_pin.json
        A fully-resolved BacktestInput + the expected BacktestResult
        the existing engine produces. Day 7 tests use this to verify
        no engine change has silently affected output.

All fixtures are committed at skeleton stage as JSON files with
placeholder schemas; Day-1 work materialises real content after the
migration applies. See README.md for the per-file shape.
"""
