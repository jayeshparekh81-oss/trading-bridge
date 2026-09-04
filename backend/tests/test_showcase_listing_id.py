"""``listing_id`` on GET /api/showcase/{key}/live — the public Subscribe target.

The showcase card needs to know which marketplace listing to send a visitor to,
without the frontend hardcoding an id. This is that lookup.

⚠️ THE MASK. s1/s2/s3 exist to hide WHICH strategy is which on a public page.
Returning ``listing_id`` makes the pairing "s1 ↔ that listing" public. The
strategy uuid prefix must still never leave the server, and that is asserted
here — the listing id is opaque, the prefix is not.

The pre-existing tests/test_showcase_api.py is broken at HEAD (7 of its 11 fail
because the artifact keys moved from "bse" to "s1" and the tests never
followed). Rather than build on a broken harness, this file carries its own.
"""

from __future__ import annotations

import asyncio

from app.api import showcase_api as api


# ── fake read-only session ─────────────────────────────────────────────────
# While the live record is UNPUBLISHED (founder gate, default) exactly ONE query
# runs inside showcase_live: the listing lookup (scalar_one_or_none). With the
# gate flipped, two count queries precede it (reconciled, human-interfered —
# both scalar_one). The fake answers them in call order.
class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value


class _Session:
    def __init__(self, *values):
        self._values = list(values)
        self.queries: list[str] = []

    async def execute(self, stmt, params=None):
        self.queries.append(str(stmt))
        self.params = params
        return _Result(self._values.pop(0) if self._values else None)


def _live(key: str, *values):
    session = _Session(*values)
    out = asyncio.run(api.showcase_live(key, session=session))
    return out, session


# ── the lookup ─────────────────────────────────────────────────────────────


def test_listing_id_is_returned_when_a_published_listing_exists():
    out, session = _live("s1", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert out["listing_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    # the honest live record beside it is the verification-period state:
    # no count, no P&L, no zero (founder, 2026-09-04)
    assert out["status"] == "verification_period"
    assert out["note"] == api.VERIFICATION_PERIOD_NOTE
    assert "reconciled_trades" not in out and "human_interfered_trades" not in out
    assert len(session.queries) == 1 and "marketplace_listings" in session.queries[0]


def test_live_record_flag_defaults_off_and_counts_only_when_published(monkeypatch):
    from app.core.config import get_settings

    assert get_settings().showcase_live_record_published is False
    settings = get_settings()
    monkeypatch.setattr(type(settings), "showcase_live_record_published", True, raising=False)
    monkeypatch.setattr(settings, "showcase_live_record_published", True, raising=False)
    out, session = _live("s1", 3, 2, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert out["status"] == "tracking_active"
    assert out["reconciled_trades"] == 3
    assert out["human_interfered_trades"] == 2  # a NULL P&L is explained, not silent
    assert "human-interfered — not attributable" in out["note"]
    assert len(session.queries) == 3


def test_listing_id_is_none_when_no_listing_exists():
    """None => the card renders NO Subscribe control, never a dead one."""
    out, _ = _live("s1", None)
    assert out["listing_id"] is None


def test_paper_strategy_never_gets_a_listing_lookup():
    """s3 has no live strategy at all (prefix None), so there is nothing to
    look up and no query is issued."""
    out, session = _live("s3")
    assert out["listing_id"] is None
    assert session.queries == []


def test_only_published_listings_qualify():
    sql = _sql_of_listing_lookup()
    assert "status = 'published'" in sql, (
        "a draft or archived listing must never become a public Subscribe "
        "target — a draft is not visible to non-owners and would 404"
    )


def test_duplicate_listings_resolve_deterministically():
    """Nothing in the schema forbids two listings on one strategy. Without an
    ORDER BY the card's target could flip between page loads."""
    sql = _sql_of_listing_lookup()
    assert "ORDER BY" in sql and "published_at" in sql
    assert "LIMIT 1" in sql


def _sql_of_listing_lookup() -> str:
    _, session = _live("s1", None)
    listing_queries = [q for q in session.queries if "marketplace_listings" in q]
    assert listing_queries, "no listing query was issued"
    return listing_queries[0]


# ── the mask ───────────────────────────────────────────────────────────────


def test_the_strategy_uuid_prefix_never_reaches_the_client():
    """The whole point of s1/s2/s3. The prefix is a join key, not public data."""
    out, _ = _live("s1", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    blob = repr(out)
    for prefix in api._LIVE_STRATEGY.values():
        if prefix:
            assert prefix not in blob, f"strategy prefix {prefix} leaked to the client"


def test_no_instrument_name_in_the_response():
    out, _ = _live("s1", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    blob = repr(out).upper()
    for name in ("BSE", "NIFTY", "BANKNIFTY", "RELIANCE"):
        assert name not in blob


# ── the router's purity contract, restated for the new query ───────────────


def test_listing_lookup_is_read_only():
    with open(api.__file__) as f:
        src = f.read()
    forbidden = [
        "INSERT", "UPDATE ", "DELETE ", ".commit(", "session.add", ".flush(",
        "strategy_executor", "direct_exit", "strategy_webhook", "kill_switch",
        "order_router", "place_order", "app.brokers",
    ]
    hits = [tok for tok in forbidden if tok in src]
    assert hits == [], f"router gained a forbidden write/trading token: {hits}"


def test_pure_loaders_still_take_no_session():
    """list_showcase and showcase_detail must stay DB-free. The listing lookup
    was deliberately put on /live, the one endpoint that already had a session,
    so the cheap endpoints stay cheap."""
    import inspect

    for fn in (api.list_showcase, api.showcase_detail):
        params = inspect.signature(fn).parameters
        assert "session" not in params, f"{fn.__name__} gained a DB session"
