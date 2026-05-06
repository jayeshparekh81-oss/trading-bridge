"use client";

import { ArrowRight, Shield, Target, Sparkles } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { GOAL_PRESETS, type BeginnerGoal } from "./presets";

interface StepPreviewProps {
  goal: BeginnerGoal;
  name: string;
  stopLossPercent: number;
  targetPercent: number;
  onNameChange: (next: string) => void;
}

export function StepPreview({
  goal,
  name,
  stopLossPercent,
  targetPercent,
  onNameChange,
}: StepPreviewProps) {
  const preset = GOAL_PRESETS[goal];
  const fast = preset.trendCompare?.fast;
  const slow = preset.trendCompare?.slow;

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold">Strategy ka preview</h2>
        <p className="text-sm text-muted-foreground">
          Aakhri check. Naam do aur backtest pe jao.
        </p>
      </div>

      {/* Name input */}
      <GlassmorphismCard hover={false}>
        <div className="space-y-2">
          <label
            htmlFor="strategy-name"
            className="text-xs uppercase tracking-wide text-muted-foreground font-medium"
          >
            Strategy Name
          </label>
          <Input
            id="strategy-name"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="My first strategy"
            maxLength={256}
            autoComplete="off"
            className="text-base"
          />
        </div>
      </GlassmorphismCard>

      {/* Entry block */}
      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="size-7 rounded-md bg-profit/15 text-profit grid place-items-center">
              <ArrowRight className="h-4 w-4" />
            </div>
            <h3 className="font-semibold text-sm">Entry — kab BUY karenge</h3>
            <Badge className="ml-auto bg-profit/15 text-profit border-profit/30 text-[10px]">
              BUY
            </Badge>
          </div>
          <div className="space-y-2">
            {fast && slow ? (
              <RuleRow
                lhs={labelFor(preset.indicators, fast)}
                op=">"
                rhs={labelFor(preset.indicators, slow)}
                hinglish="Tej trend slow trend ke upar hona chahiye (uptrend confirm)."
              />
            ) : null}
            <RuleRow
              lhs={labelFor(preset.indicators, preset.rsiId)}
              op="<"
              rhs="30"
              hinglish="RSI oversold zone mein — bhaav neeche aaya hai, bounce ka chance."
            />
          </div>
          <div className="flex items-center gap-2 pt-1">
            <span className="text-[11px] text-muted-foreground uppercase tracking-wide">
              Combined with
            </span>
            <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px]">
              AND
            </Badge>
            <span className="text-[11px] text-muted-foreground">
              (Sab condition match honi chahiye.)
            </span>
          </div>
        </div>
      </GlassmorphismCard>

      {/* Exit block */}
      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="size-7 rounded-md bg-loss/15 text-loss grid place-items-center">
              <ArrowRight className="h-4 w-4 -rotate-45" />
            </div>
            <h3 className="font-semibold text-sm">Exit — kab nikalenge</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <ExitTile
              icon={<Target className="h-4 w-4 text-profit" />}
              title="Target"
              value={`+${targetPercent}%`}
              hinglish={`${targetPercent}% profit milte hi book karo.`}
            />
            <ExitTile
              icon={<Shield className="h-4 w-4 text-loss" />}
              title="Stop Loss"
              value={`-${stopLossPercent}%`}
              hinglish={`${stopLossPercent}% loss pe nikal jao — discipline.`}
            />
          </div>
        </div>
      </GlassmorphismCard>

      <div className="rounded-lg bg-accent-blue/5 border border-accent-blue/20 px-3 py-2.5 flex items-start gap-2">
        <Sparkles className="h-4 w-4 text-accent-blue shrink-0 mt-0.5" />
        <p className="text-xs text-muted-foreground leading-relaxed">
          Yeh paper backtest mode mein chalega — real paisa nahi lagta.
          Backtest se confidence aane ke baad hi paper/live pe jao.
        </p>
      </div>
    </div>
  );
}


function labelFor(
  inds: { id: string; label: string }[],
  id: string,
): string {
  return inds.find((i) => i.id === id)?.label ?? id;
}


interface RuleRowProps {
  lhs: string;
  op: string;
  rhs: string;
  hinglish: string;
}

function RuleRow({ lhs, op, rhs, hinglish }: RuleRowProps) {
  return (
    <div className="rounded-md bg-white/[0.02] border border-white/[0.04] p-3 space-y-1.5">
      <div className="flex items-center gap-2 flex-wrap text-sm font-medium">
        <span className="px-2 py-0.5 rounded bg-accent-blue/10 text-accent-blue text-xs">
          {lhs}
        </span>
        <span className="text-muted-foreground font-mono">{op}</span>
        <span className="px-2 py-0.5 rounded bg-white/[0.06] text-foreground text-xs">
          {rhs}
        </span>
      </div>
      <p className="text-[11px] text-muted-foreground leading-snug">
        {hinglish}
      </p>
    </div>
  );
}


interface ExitTileProps {
  icon: React.ReactNode;
  title: string;
  value: string;
  hinglish: string;
}

function ExitTile({ icon, title, value, hinglish }: ExitTileProps) {
  return (
    <div className="rounded-md bg-white/[0.02] border border-white/[0.04] p-3 space-y-1">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-xs uppercase tracking-wide text-muted-foreground">
          {title}
        </span>
        <span className="ml-auto text-base font-semibold tabular-nums">
          {value}
        </span>
      </div>
      <p className="text-[11px] text-muted-foreground leading-snug">
        {hinglish}
      </p>
    </div>
  );
}
