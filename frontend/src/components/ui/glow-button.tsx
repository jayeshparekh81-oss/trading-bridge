"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import type { ButtonHTMLAttributes, ReactNode } from "react";

interface GlowButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: "primary" | "profit" | "danger";
  size?: "sm" | "md" | "lg";
}

const variants = {
  primary:
    "bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-[0_0_25px_rgba(59,130,246,0.4)]",
  profit:
    "bg-gradient-to-r from-emerald-500 to-profit hover:shadow-[0_0_25px_rgba(0,255,136,0.3)]",
  danger:
    "bg-gradient-to-r from-red-500 to-loss hover:shadow-[0_0_25px_rgba(255,77,106,0.3)]",
};

const sizes = {
  sm: "px-4 py-2 text-sm",
  md: "px-6 py-3 text-base",
  lg: "px-8 py-4 text-lg",
};

export function GlowButton({
  children,
  variant = "primary",
  size = "md",
  className,
  ...props
}: GlowButtonProps) {
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className={cn(
        "rounded-xl font-semibold text-white transition-all duration-300",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className
      )}
      {...(props as Record<string, unknown>)}
    >
      {children}
    </motion.button>
  );
}
