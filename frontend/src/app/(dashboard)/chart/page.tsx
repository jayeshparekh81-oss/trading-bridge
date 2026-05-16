/**
 * /chart — Day-5 chart page + Phase D Strategy Tester panel.
 *
 * Phase D (May 16): Strategy Tester panel rendered below the chart.
 * Wrapper uses min-h to prevent recharts from collapsing to 0
 * dimensions when parent flex doesn't push expected height.
 */

"use client";

import { ChartContainer } from "@/components/chart/ChartContainer";
import { StrategyTesterPanel } from "@/components/strategy-tester/StrategyTesterPanel";

const MVP_STRATEGY_ID = "89423ecc-c76e-432c-b107-0791508542f0";

export default function ChartPage() {
  return (
    <div className="flex flex-col gap-6 pb-12">
      <div className="min-h-[700px]">
        <ChartContainer />
      </div>
      <div className="min-h-[800px] w-full border-t border-white/10 pt-6">
        <StrategyTesterPanel strategyId={MVP_STRATEGY_ID} mode="PAPER" />
      </div>
    </div>
  );
}
