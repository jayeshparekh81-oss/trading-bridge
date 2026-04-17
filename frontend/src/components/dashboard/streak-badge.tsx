"use client";

import { motion } from "framer-motion";

interface StreakBadgeProps {
  streak: number;
}

export function StreakBadge({ streak }: StreakBadgeProps) {
  if (streak <= 0) return null;

  const trophies = Array.from({ length: Math.min(streak, 5) }, (_, i) => i);

  return (
    <motion.div
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      transition={{ type: "spring", stiffness: 300, delay: 0.5 }}
      className="flex items-center gap-1"
    >
      {trophies.map((i) => (
        <motion.span
          key={i}
          initial={{ scale: 0, rotate: -20 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ delay: 0.6 + i * 0.1, type: "spring" }}
          className="text-lg"
        >
          {"\uD83C\uDFC6"}
        </motion.span>
      ))}
    </motion.div>
  );
}
