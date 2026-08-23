"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";

interface GlowButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Optional so the component can be used as a base-ui ``render`` element,
   *  where the primitive injects children itself. */
  children?: ReactNode;
  variant?: "primary" | "profit" | "danger";
  size?: "sm" | "md" | "lg";
  /**
   * React 19 passes ``ref`` as a normal prop to function components, so no
   * forwardRef is needed. It MUST be accepted and forwarded to the underlying
   * button: base-ui primitives (Dialog/Popover/Tooltip/Sheet) attach their
   * trigger ref here when this component is passed via ``render``. Dropping it
   * breaks open-on-click and positioning.
   */
  ref?: Ref<HTMLButtonElement>;
}

const variants = {
  primary:
    "bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-[0_0_25px_rgba(0,255,136,0.4)]",
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
  ref,
  ...props
}: GlowButtonProps) {
  return (
    <motion.button
      ref={ref}
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
