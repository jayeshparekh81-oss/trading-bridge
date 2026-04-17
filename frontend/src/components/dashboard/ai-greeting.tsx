"use client";

import { motion } from "framer-motion";
import { getGreeting, formatCurrency } from "@/lib/utils";

interface AiGreetingProps {
  name: string;
  todayPnl: number;
}

export function AiGreeting({ name, todayPnl }: AiGreetingProps) {
  const greeting = getGreeting();
  const isProfit = todayPnl >= 0;
  const emoji = isProfit ? "\uD83C\uDF89" : "\uD83D\uDCAA";
  const message = isProfit
    ? `Your strategies earned ${formatCurrency(todayPnl)}. Great day!`
    : `Down ${formatCurrency(Math.abs(todayPnl))} today. Tomorrow is a new opportunity.`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="mb-6"
    >
      <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
        {greeting},{" "}
        <span className="bg-gradient-to-r from-accent-blue to-accent-purple bg-clip-text text-transparent">
          {name}
        </span>
        !
      </h1>
      <p className="text-muted-foreground mt-1">
        {message} {emoji}
      </p>
    </motion.div>
  );
}
