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
        "rounded-xl border border-white/[0.08] bg-card/60 backdrop-blur-xl p-6",
        "dark:bg-[#111827]/60 dark:border-white/[0.08]",
        "light:bg-white/80 light:border-black/[0.06]",
        glowClass,
        className
      )}
    >
      {children}
    </motion.div>
  );
}
