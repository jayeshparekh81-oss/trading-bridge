/**
 * /chart — Day-5 chart page + Phase D Strategy Tester panel.
 *
 * Phase D (May 16): Strategy Tester panel rendered below the chart.
 * Wrapper uses min-h to prevent recharts from collapsing to 0
 * dimensions when parent flex doesn't push expected height.
 */

"use client";

import { useState } from "react";

import { ChartContainer } from "@/components/chart/ChartContainer";
import { StrategyTesterPanel } from "@/components/strategy-tester/StrategyTesterPanel";

/**
 * The Strategy Tester follows the strategy the CUSTOMER picks in the chart's
 * own selector. It used to be pinned to a hardcoded id — the founder's live
 * BSE strategy — for every visitor, which fired three 403s on every chart
 * load (the tester endpoints are ownership-gated) and put a live-money
 * strategy id in every customer's browser. No selection → no tester.
 */
export default function ChartPage() {
  const [strategyId, setStrategyId] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-6 pb-12">
      <div className="min-h-[700px]">
        <ChartContainer onStrategyChange={setStrategyId} />
      </div>
      {strategyId ? (
        <div className="min-h-[800px] w-full border-t border-white/10 pt-6">
          <StrategyTesterPanel strategyId={strategyId} mode="PAPER" />
        </div>
      ) : (
        <p
          className="text-xs text-muted-foreground border-t border-white/10 pt-6"
          data-testid="chart-tester-hint"
        >
          Pick one of your strategies above to see its paper trades, equity curve and
          metrics here.
        </p>
      )}
    </div>
  );
}
