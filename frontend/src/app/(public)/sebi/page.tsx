import { LegalPage, LegalSection } from "@/components/legal/legal-page";

export default function SebiInfoPage() {
  return (
    <LegalPage accent="SEBI" rest=" Info" kind="SEBI / compliance document">
      <LegalSection title="The framework">
        <p>
          The SEBI algorithmic-trading framework (Feb 2025, enforceable from 2026) governs how
          algo trading is offered to retail investors in India. A core principle is
          transparency — retail algo strategies should be auditable, not opaque black boxes.
        </p>
      </LegalSection>

      <LegalSection title="How TRADETRI aligns">
        <p>
          TRADETRI is built white-box: every signal carries a transparent, rule-based
          conviction score you can inspect — not a hidden model. Trades route through your own
          SEBI-registered broker, and TRADETRI never holds or withdraws your funds.
        </p>
      </LegalSection>

      <LegalSection title="Our status — stated honestly">
        <p>
          TRADETRI is SEBI-aware. It is NOT a SEBI-registered investment adviser, and is NOT
          (yet) empanelled as an algorithmic-trading provider with the exchanges. AlgoMitra,
          our in-app assistant, is advisory and educational only — it never executes trades
          autonomously.
        </p>
      </LegalSection>

      <LegalSection title="Informational only">
        <p>
          This page is informational, not legal or regulatory advice. A detailed compliance
          document is being finalised.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
