"use client";

import { cn } from "@/lib/utils";
import { AnimatedNumber } from "./animated-number";

interface ProfitLossTextProps {
  value: number;
  size?: "sm" | "md" | "lg" | "hero";
  showSign?: boolean;
  glow?: boolean;
  animated?: boolean;
  className?: string;
}

const sizeClasses = {
  sm: "text-sm font-medium",
  md: "text-lg font-semibold",
  lg: "text-2xl font-bold",
  hero: "text-5xl font-bold tracking-tight",
};

export function ProfitLossText({
  value,
  size = "md",
  showSign = true,
  glow = false,
  animated = true,
  className,
}: ProfitLossTextProps) {
  const isProfit = value >= 0;
  const colorClass = isProfit ? "text-profit" : "text-loss";
  const glowClass = glow ? (isProfit ? "glow-profit" : "glow-loss") : "";
  const sign = showSign && value > 0 ? "+" : "";

  if (animated) {
    return (
      <AnimatedNumber
        value={value}
        prefix={`${sign}\u20B9`}
        className={cn(sizeClasses[size], colorClass, glowClass, className)}
        locale="en-IN"
      />
    );
  }

  const formatted = Math.abs(value).toLocaleString("en-IN");
  return (
    <span className={cn(sizeClasses[size], colorClass, glowClass, className)}>
      {sign}
      {value < 0 ? "-" : ""}
      {"\u20B9"}
      {formatted}
    </span>
  );
}
