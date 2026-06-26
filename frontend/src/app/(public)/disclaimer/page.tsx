import Link from "next/link";
import { LegalPage, LegalSection } from "@/components/legal/legal-page";

export default function DisclaimerPage() {
  return (
    <LegalPage accent="Risk" rest=" Disclaimer" kind="risk disclaimer">
      <LegalSection title="Capital is at risk">
        <p>
          Trading and investing involve a substantial risk of loss. You can lose some or all
          of your capital. Only trade with money you can afford to lose.
        </p>
      </LegalSection>

      <LegalSection title="No guarantees, not advice">
        <p>
          Past performance is not indicative of future results. Nothing on TRADETRI is
          investment advice or a recommendation. TRADETRI provides white-box (transparent)
          strategies and makes no guaranteed-return claims.
        </p>
      </LegalSection>

      <LegalSection title="Backtests are hypothetical">
        <p>
          Any backtested figures are hypothetical, prepared with hindsight, involve no real
          risk, exclude slippage (so they are best-case), are in-sample, and frequently differ
          from real results.
        </p>
      </LegalSection>

      <LegalSection title="Your broker, your funds">
        <p>
          Trades route through your own exchange-registered broker. TRADETRI never holds your
          funds, and you remain responsible for your account and decisions.
        </p>
      </LegalSection>

      <LegalSection title="Regulatory note">
        <p>
          TRADETRI operates in line with the spirit of the SEBI algorithmic-trading framework
          and is SEBI-aware. It is not a SEBI-registered investment adviser, and is not (yet)
          empanelled as an algo provider — see the{" "}
          <Link href="/sebi" className="text-accent-blue hover:underline">
            SEBI Info
          </Link>{" "}
          page.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
