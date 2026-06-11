"use client";

/**
 * Beginner wizard — Step 5 "Deploy".
 *
 * Lives inside the wizard so the user is no longer dumped onto the
 * standalone strategy-detail page after their first build. Renders the
 * SAME deploy/activate surface that the strategy-detail page uses
 * (``SafetyPreFlightPanel`` + ``GoLiveButton`` + ``GoLiveModal`` +
 * ``OrderResultCard``) — no new activation logic, no copy of the API
 * calls. Paper-mode behaviour is owned entirely by ``GoLiveModal``
 * (which forces ``dryRun=true`` when the platform is in paper mode),
 * so this component does not touch ``is_paper`` semantics.
 *
 * The "View backtest result" link is the secondary CTA so the user can
 * still reach the existing backtest page when they want to — same
 * destination the old wizard's final step pushed to automatically.
 */

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  PartyPopper,
  PlayCircle,
  Rocket,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import {
  SafetyPreFlightPanel,
  type SafetyChainResult,
} from "@/components/strategies/safety-pre-flight-panel";
import { GoLiveButton } from "@/components/strategies/go-live-button";
import {
  GoLiveModal,
  type LiveOrderResult,
} from "@/components/strategies/go-live-modal";
import { OrderResultCard } from "@/components/strategies/order-result-card";

interface StepDeployProps {
  strategyId: string;
  strategyName: string;
  /** Wizard footer back arrow — returns to step 4 (Run) so the user can
   *  re-submit if they want to tweak something. Builder reducer owns the
   *  back transition; this component only fires the callback. */
  onBack: () => void;
}

export function StepDeploy({
  strategyId,
  strategyName,
  onBack,
}: StepDeployProps) {
  const [preflight, setPreflight] = useState<SafetyChainResult | null>(null);
  const [preflightLoaded, setPreflightLoaded] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [latestResult, setLatestResult] = useState<LiveOrderResult | null>(
    null,
  );

  function handlePreflight(result: SafetyChainResult) {
    setPreflight(result);
    setPreflightLoaded(true);
  }

  function handleResult(result: LiveOrderResult) {
    setLatestResult(result);
  }

  function handlePlaceAnother() {
    setLatestResult(null);
    setModalOpen(true);
  }

  return (
    <div className="space-y-5">
      {/* Celebration card — wizard finish line. */}
      <GlassmorphismCard hover={false} glow="blue">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-blue/15 text-accent-blue">
            <PartyPopper className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <h2 className="text-lg font-semibold leading-tight">
              Strategy ban gayi
            </h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              <span className="text-foreground font-medium">
                {strategyName}
              </span>{" "}
              save ho gayi. Ab safety checks dekho aur ek dry-run order
              place karke confidence build karo. Live order tabhi enable
              hota hai jab saare checks pass ho.
            </p>
          </div>
        </div>
      </GlassmorphismCard>

      {/* Deploy section — reuses the exact same composition the
          strategy-detail page wires together so the deploy contract +
          paper-mode default + safety chain stay in one place. */}
      <section className="space-y-3" aria-label="Deploy strategy">
        <div className="flex items-center gap-2">
          <Rocket className="h-4 w-4 text-accent-purple" />
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Live Trading
          </h3>
        </div>

        <SafetyPreFlightPanel
          strategyId={strategyId}
          onResult={handlePreflight}
        />

        <div className="flex justify-end">
          <GoLiveButton
            preflight={preflight}
            isPreflightLoading={!preflightLoaded}
            onClick={() => setModalOpen(true)}
          />
        </div>

        {latestResult ? (
          <OrderResultCard
            result={latestResult}
            strategyId={strategyId}
            onPlaceAnother={handlePlaceAnother}
          />
        ) : null}

        <GoLiveModal
          open={modalOpen}
          onOpenChange={setModalOpen}
          strategyId={strategyId}
          strategyName={strategyName}
          preflight={preflight}
          onResult={handleResult}
        />
      </section>

      {/* Footer — Back to Run + the secondary "View backtest" link
          that the old wizard would push to automatically. */}
      <div className="flex items-center justify-between gap-3 pt-2 flex-wrap">
        <Button variant="ghost" size="sm" type="button" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <Link
          href={`/strategies/${strategyId}/backtest`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-accent-blue hover:underline underline-offset-4"
          data-testid="step-deploy-view-backtest"
        >
          <PlayCircle className="h-4 w-4" />
          View backtest result
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
