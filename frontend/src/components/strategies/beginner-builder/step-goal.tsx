"use client";

import { Zap, TrendingUp, Rocket, GraduationCap, Check } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { GOAL_CARDS, type BeginnerGoal } from "./presets";

const ICONS: Record<BeginnerGoal, React.ComponentType<{ className?: string }>> = {
  intraday: Zap,
  swing: TrendingUp,
  scalping: Rocket,
  safe: GraduationCap,
};

interface StepGoalProps {
  selected: BeginnerGoal | null;
  onSelect: (goal: BeginnerGoal) => void;
}

export function StepGoal({ selected, onSelect }: StepGoalProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold">
          Aapka goal kya hai?
        </h2>
        <p className="text-sm text-muted-foreground">
          Pick one. We&apos;ll set up the rest. You can always change it later.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {GOAL_CARDS.map((card) => {
          const Icon = ICONS[card.id];
          const isSelected = card.id === selected;
          return (
            <button
              key={card.id}
              type="button"
              onClick={() => onSelect(card.id)}
              aria-pressed={isSelected}
              className="text-left"
            >
              <GlassmorphismCard
                hover
                glow={isSelected ? "blue" : "none"}
                className={cn(
                  "h-full transition-all",
                  isSelected
                    ? "ring-2 ring-accent-blue/50"
                    : "hover:ring-1 hover:ring-white/10",
                )}
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div
                      className={cn(
                        "size-10 rounded-lg grid place-items-center",
                        isSelected
                          ? "bg-accent-blue/20 text-accent-blue"
                          : "bg-white/[0.04] text-muted-foreground",
                      )}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    {isSelected ? (
                      <div className="size-6 rounded-full bg-accent-blue text-white grid place-items-center">
                        <Check className="h-3.5 w-3.5" />
                      </div>
                    ) : (
                      <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
                        {card.badge}
                      </Badge>
                    )}
                  </div>
                  <div className="space-y-1">
                    <h3 className="font-semibold text-base">{card.title}</h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {card.blurb}
                    </p>
                  </div>
                  <div className="rounded-md bg-white/[0.02] border border-white/[0.04] px-3 py-2">
                    <p className="text-[11px] text-muted-foreground leading-snug">
                      <span className="text-accent-blue font-medium">Hinglish:</span>{" "}
                      {card.hinglish}
                    </p>
                  </div>
                </div>
              </GlassmorphismCard>
            </button>
          );
        })}
      </div>
    </div>
  );
}
