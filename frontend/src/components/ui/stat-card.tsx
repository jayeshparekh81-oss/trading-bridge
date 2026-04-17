"use client";

import { cn } from "@/lib/utils";
import { GlassmorphismCard } from "./glassmorphism-card";
import { AnimatedNumber } from "./animated-number";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: number | string;
  suffix?: string;
  prefix?: string;
  trend?: "up" | "down" | "neutral";
  iconColor?: string;
  className?: string;
}

export function StatCard({
  icon: Icon,
  label,
  value,
  suffix,
  prefix,
  trend,
  iconColor = "text-accent-blue",
  className,
}: StatCardProps) {
  return (
    <GlassmorphismCard className={cn("p-5", className)}>
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">{label}</p>
          <div className="text-2xl font-bold tracking-tight">
            {typeof value === "number" ? (
              <AnimatedNumber
                value={value}
                prefix={prefix}
                suffix={suffix}
              />
            ) : (
              <span>
                {prefix}
                {value}
                {suffix}
              </span>
            )}
          </div>
        </div>
        <div
          className={cn(
            "rounded-lg p-2.5 bg-white/[0.05]",
            iconColor
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </GlassmorphismCard>
  );
}
