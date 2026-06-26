import Link from "next/link";
import { LegalPage, LegalSection } from "@/components/legal/legal-page";

export default function TermsPage() {
  return (
    <LegalPage accent="Terms" rest=" of Service" kind="Terms of Service">
      <LegalSection title="What TRADETRI is">
        <p>
          TRADETRI is a transparent, white-box algo-trading platform. You connect your own
          broker account, and signals (for example, from TradingView) are routed to that
          broker as orders. TRADETRI is a tool — not a guarantee of profit.
        </p>
      </LegalSection>

      <LegalSection title="Your responsibility">
        <p>
          You are responsible for your own trading decisions, your broker account, your
          capital, and any resulting gains or losses. Keep your account and broker
          credentials secure, and use the platform lawfully.
        </p>
      </LegalSection>

      <LegalSection title="Your funds stay with your broker">
        <p>
          Trades execute in your own exchange-registered broker account. TRADETRI never
          holds, custodies, or withdraws your funds.
        </p>
      </LegalSection>

      <LegalSection title="Subscriptions & billing">
        <p>
          Paid subscription plans are listed on the{" "}
          <Link href="/pricing" className="text-accent-blue hover:underline">
            Pricing
          </Link>{" "}
          page. Full subscription, billing, and cancellation terms are being finalised and
          will appear in the complete Terms.
        </p>
      </LegalSection>

      <LegalSection title="Service availability">
        <p>
          The service is provided on an as-is basis. We work hard for reliability but do not
          guarantee uninterrupted or error-free operation.
        </p>
      </LegalSection>

      <LegalSection title="Full terms coming">
        <p>
          This is an interim summary. A complete Terms of Service document is being finalised
          and will replace this page.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
