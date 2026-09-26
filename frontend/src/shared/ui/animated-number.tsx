"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";

interface AnimatedNumberProps {
  value: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  decimals?: number;
  locale?: string;
}

export function AnimatedNumber({
  value,
  duration = 1.5,
  prefix = "",
  suffix = "",
  className,
  decimals = 0,
  locale = "en-IN",
}: AnimatedNumberProps) {
  // The REAL value from the very first paint (founder's rule, 26 Sep, point 10:
  // nothing that looks like data but isn't). This used to start at 0 and count up
  // only once scrolled into view — so the server page read "0 Years engineering",
  // and a P&L below the fold showed ₹0 until the customer scrolled to it.
  // Now a change animates from the LAST REAL value to the new one; never from 0.
  const [displayValue, setDisplayValue] = useState(value);
  const shown = useRef(value);
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true });

  useEffect(() => {
    const start = shown.current;
    const end = value;
    if (start === end) return;
    const startTime = performance.now();
    const durationMs = duration * 1000;
    let frame = 0;

    function animate(currentTime: number) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const v = start + (end - start) * eased;
      shown.current = v;
      setDisplayValue(v);
      if (progress < 1) frame = requestAnimationFrame(animate);
    }

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);

  const formatted = Math.abs(displayValue).toLocaleString(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return (
    <motion.span
      ref={ref}
      initial={{ opacity: 0, y: 10 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.4 }}
      className={className}
    >
      {prefix}
      {displayValue < 0 && Math.abs(displayValue) >= 0.5 * 10 ** -decimals ? "-" : ""}
      {formatted}
      {suffix}
    </motion.span>
  );
}
