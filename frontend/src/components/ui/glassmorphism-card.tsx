"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface GlassmorphismCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  glow?: "profit" | "loss" | "blue" | "none";
}

export function GlassmorphismCard({
  children,
  className,
  hover = true,
  glow = "none",
}: GlassmorphismCardProps) {
  const glowClass = {
    profit: "glow-border-profit",
    loss: "border-loss/30",
    blue: "glow-border-blue",
    none: "",
  }[glow];

  return (
    <motion.div
      whileHover={hover ? { y: -2, scale: 1.005 } : undefined}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={cn(
        "rounded-xl p-6 transition-colors",
        // Dark: glass blur + subtle border
        "dark:bg-card/60 dark:backdrop-blur-xl dark:border dark:border-border",
        // Light: solid card + soft shadow (Zerodha/CRED style)
        "bg-card border border-border shadow-[0_1px_3px_rgba(0,0,0,0.04),0_4px_16px_rgba(0,0,0,0.03)]",
        "dark:shadow-none",
        glowClass,
        className
      )}
    >
      {children}
    </motion.div>
  );
}
