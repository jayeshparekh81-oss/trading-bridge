"use client";

/**
 * AlgoMitra toggle button — floating right-edge affordance shown
 * when the Always-On panel is closed. Click re-opens the panel.
 *
 * Positioned right-edge / vertically-centered so it doesn't collide
 * with the existing :class:`ChatWidget` (bottom-right) or the
 * mobile bottom-nav. Native ``title`` attribute carries the Hinglish
 * tooltip without requiring a Tooltip provider.
 */

import { motion } from "framer-motion";
import { Bot } from "lucide-react";
import { cn } from "@/lib/utils";

interface AlgoMitraToggleButtonProps {
  onClick: () => void;
}

export function AlgoMitraToggleButton({
  onClick,
}: AlgoMitraToggleButtonProps) {
  return (
    <motion.button
      key="algomitra-toggle"
      initial={{ x: 64, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 64, opacity: 0 }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      type="button"
      onClick={onClick}
      title="AlgoMitra Coach kholo"
      aria-label="Open AlgoMitra coaching panel"
      className={cn(
        "fixed right-3 top-1/2 -translate-y-1/2 z-40",
        "size-12 rounded-full",
        "bg-gradient-to-br from-accent-blue to-accent-purple",
        "shadow-[0_0_25px_rgba(168,85,247,0.45)]",
        "grid place-items-center",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-purple/60",
      )}
    >
      <Bot className="h-5 w-5 text-white" />
      <span className="sr-only">Show AlgoMitra Coach</span>
    </motion.button>
  );
}
