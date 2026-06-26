import { LegalPage, LegalSection } from "@/components/legal/legal-page";

export default function PrivacyPage() {
  return (
    <LegalPage accent="Privacy" rest=" Policy" kind="Privacy Policy">
      <LegalSection title="What we collect">
        <p>
          To run the service we collect your account details (such as your email), the broker
          API credentials you choose to connect (stored encrypted), and basic usage data
          needed to operate your account.
        </p>
      </LegalSection>

      <LegalSection title="How we use it">
        <p>
          We use this data only to connect your broker, route your signals to orders, and
          operate and support your account.
        </p>
      </LegalSection>

      <LegalSection title="Your funds & credentials">
        <p>
          Broker credentials are encrypted at rest. TRADETRI never holds or withdraws your
          funds — trades execute in your own broker account. We do not sell your data.
        </p>
      </LegalSection>

      <LegalSection title="What we are not claiming here">
        <p>
          This interim summary does not assert specific certifications or data-retention
          periods — those will be stated accurately in the finalised policy, rather than
          guessed at here.
        </p>
      </LegalSection>

      <LegalSection title="Full policy coming">
        <p>
          A complete Privacy Policy is being finalised and will replace this page. For any
          question about your data, email us.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
