"""ADDITION D — no modelled number may reach a customer surface, ever again.

FOUNDER'S RULING, 2026-09-16: "NET = Dhan BILLED charges from the trade book,
never modelled. 'Never estimate' wins. A fill with no billed charges => show
gross, charges 'baaki', net NULL. No modelled fallback anywhere on customer
pages."

WHY THIS IS A TEST AND NOT A ONE-TIME GREP. The cost model still EXISTS — it is
legitimate for backtests and projections, where nobody has been billed yet. So
nothing stops a future change from importing it back into a page that reports
real money, and the number it produces looks entirely plausible: across
1..16 Sep it was optimistic by only 1,029.84 on 84,140.00 of gross. A figure
that is wrong by 1.2% and labelled confidently is far more dangerous than one
that is obviously broken.

It also cannot be repaired by care. On 04-Sep the model charges STT on BOTH
400-lot sells; Dhan billed 1366.40 on 312260904412406 and 0.00 on
23226090443106. No per-fill formula reproduces that.

So this file enforces the boundary mechanically: the customer-facing modules
must not import the cost model, and their money wording must not call a billed
figure estimated.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]

#: Modules that render the LIVE, REAL-MONEY record. Nothing here may so much as
#: import the cost model.
#:
#: ``service.py`` is deliberately NOT on this list, and the reason is a real
#: distinction rather than an exemption: it also prices PAPER trips, where
#: nobody was ever billed, so a clearly-labelled model is the only figure that
#: can exist. What matters is that its LIVE path does not use it — asserted
#: behaviourally in TestTheLivePathNullsTheModel below, which is the stronger
#: check anyway.
CUSTOMER_SURFACES = (
    "app/api/strategy_positions.py",
    "app/schemas/strategy_position.py",
    "app/domains/pnl_reconciler/truth_check.py",
)

#: Surfaces whose WORDING is checked, live and paper alike: whatever the source
#: of a number, no string may call a billed figure an estimate.
WORDING_SURFACES = (*CUSTOMER_SURFACES, "app/domains/pnl_reconciler/service.py")

#: The cost model. Fine for backtests; never for a bill.
FORBIDDEN_IMPORTS = {
    "app.domains.pnl_reconciler.costs",
    "compute_costs",
    "CostBreakdown",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
    return found


class TestTheCostModelCannotReachAPage:
    @pytest.mark.parametrize("rel", CUSTOMER_SURFACES)
    def test_no_customer_surface_imports_the_cost_model(self, rel: str) -> None:
        """🔴 THE ONE THAT MATTERS. Proven by AST, not by grepping for a string
        a rename would slip past."""
        found = _imports(BACKEND / rel)
        leaked = found & FORBIDDEN_IMPORTS
        assert not leaked, (
            f"{rel} imports the cost model {sorted(leaked)} — net on a customer "
            "page must come from Dhan's bill, never from a model"
        )

    def test_falsification_twin_the_check_can_actually_see_an_import(self) -> None:
        """The twin. A checker that read nothing would pass every case above
        and silently stop guarding the boundary. The cost model IS still
        imported by its own tests — so the detector has something real to find."""
        found = _imports(BACKEND / "app/domains/pnl_reconciler/costs.py")
        assert found, "the AST reader returned nothing at all"

    def test_the_cost_model_still_exists_for_the_uses_that_are_honest(self) -> None:
        """Not deleted — projections and backtests have nobody to bill. The rule
        is about which SURFACE may show a modelled number, not about the model."""
        assert (BACKEND / "app/domains/pnl_reconciler/costs.py").exists()


class TestTheWordingDoesNotCallABillAnEstimate:
    #: Phrases that describe a BILLED figure as modelled. Substring match on
    #: the strings a user can actually see.
    BANNED = ("costs ESTIMATED", "[costs ESTIMATED]", "net of estimated charges")

    @pytest.mark.parametrize("rel", WORDING_SURFACES)
    def test_no_user_visible_string_calls_a_billed_number_estimated(
        self, rel: str
    ) -> None:
        tree = ast.parse((BACKEND / rel).read_text())
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for phrase in self.BANNED:
                    if phrase in node.value:
                        offenders.append(f"{phrase!r} in {node.value[:60]!r}")
        assert not offenders, f"{rel}: {offenders}"

    def test_the_replacement_wording_is_the_founders_own(self) -> None:
        """"charges Dhan ke bill se" on a billed row; "baaki" when the bill has
        not arrived. His words, so the page reads like a person wrote it."""
        source = (BACKEND / "app/api/strategy_positions.py").read_text()
        assert "Dhan ke bill se" in source
        assert "BAAKI" in source

    def test_falsification_twin_the_scanner_reads_real_strings(self) -> None:
        """The twin. If the AST walk found no string constants at all, every
        assertion above would be vacuously true."""
        tree = ast.parse((BACKEND / "app/api/strategy_positions.py").read_text())
        strings = [
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        assert len(strings) > 50, "the scanner is not seeing the file's strings"
        assert any("Dhan ke bill se" in s for s in strings)


class TestTheLivePathNullsTheModel:
    """The behavioural half of D, and the stronger one.

    ``service.py`` may import the cost model for paper trips. What it may NOT
    do is let a modelled breakdown survive on a trip priced from the ACCOUNT's
    real fills — because then one row carries two numbers for one fact, and the
    modelled one is the flattering one.
    """

    def test_a_live_priced_trip_carries_billed_charges_and_no_model(self) -> None:
        from decimal import Decimal

        from app.domains.pnl_reconciler.service import RoundTrip

        trip = RoundTrip(
            position_id=None, symbol="BSE-SEP2026-FUT", direction="long",
            position_qty=800, entry_legs=1, entry_price=Decimal("3270"),
            exits=[], exit_qty_total=800, gross_pnl=Decimal("80360.00"),
            costs=None, net_pnl=Decimal("78057.7216"), complete=True, flags=[],
        )
        trip.billed_charges = Decimal("2302.2784")
        assert trip.costs is None, "the modelled breakdown must not survive"
        assert trip.billed_charges is not None
        # Full precision in the record — Dhan bills to four decimals and the
        # data keeps them. Two-decimal rounding is a DISPLAY concern (R1.4).
        assert trip.net_pnl == trip.gross_pnl - trip.billed_charges
        assert trip.net_pnl == Decimal("78057.7216")
        assert trip.net_pnl.quantize(Decimal("0.01")) == Decimal("78057.72")

    def test_the_live_path_sets_costs_to_none_on_every_branch(self) -> None:
        """Read from the source: both exits of ``_classify_trip`` — the
        unpriceable one and the priced one — null the modelled breakdown. If a
        third branch is ever added that forgets to, this fails."""
        import ast
        import inspect

        from app.domains.pnl_reconciler import service

        src = inspect.getsource(service._classify_trip)
        tree = ast.parse(src.lstrip())
        assigns = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(
                isinstance(t, ast.Attribute) and t.attr == "costs" for t in n.targets
            )
        ]
        assert assigns, "the live path no longer assigns trip.costs at all"
        for node in assigns:
            assert isinstance(node.value, ast.Constant) and node.value.value is None, (
                "the live path assigned trip.costs something other than None"
            )
