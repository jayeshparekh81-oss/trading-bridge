/**
 * Celebration primitives — confetti bursts that scale with the magnitude
 * of the moment.
 *
 * Locked emoji + density scaling (see ``prompts/master-plan-final.md``
 * "Hypnotic Frontend Polish"):
 *
 *   small  ▸ 30 particles, 0.5s     — strategy saved, indicator added
 *   medium ▸ 80 particles, 1.0s     — profitable backtest, paper success
 *   big    ▸ 150 particles, 1.5s    — Trust Score A, Live Ready unlock
 *   huge   ▸ 250 particles, 2-3s    — first live profit, milestone
 *
 * The hook respects ``prefers-reduced-motion`` — when the user has
 * requested reduced motion the burst is silently a no-op so toasts /
 * copy still convey the same information without the dopamine animation.
 */

import { useCallback } from "react";
import { useReducedMotion } from "framer-motion";

export type CelebrationLevel = "small" | "medium" | "big" | "huge";

interface CelebrationPreset {
  particleCount: number;
  spread: number;
  startVelocity: number;
  ticks: number;
  scalar: number;
  /** Approximate animation duration in milliseconds — caller can use
   *  this to coordinate sustained CSS glows (see ``celebrate-sustained``
   *  in globals.css). */
  durationMs: number;
}

const PRESETS: Record<CelebrationLevel, CelebrationPreset> = {
  small: {
    particleCount: 30,
    spread: 50,
    startVelocity: 25,
    ticks: 80,
    scalar: 0.8,
    durationMs: 500,
  },
  medium: {
    particleCount: 80,
    spread: 70,
    startVelocity: 35,
    ticks: 130,
    scalar: 0.9,
    durationMs: 1000,
  },
  big: {
    particleCount: 150,
    spread: 90,
    startVelocity: 45,
    ticks: 180,
    scalar: 1.0,
    durationMs: 1500,
  },
  huge: {
    particleCount: 250,
    spread: 120,
    startVelocity: 55,
    ticks: 240,
    scalar: 1.1,
    durationMs: 2500,
  },
};

/** Indian-fintech brand palette for the confetti — green/saffron/blue. */
const COLORS = ["#39FF14", "#FF9933", "#FFFFFF", "#138808", "#3B82F6"];

/**
 * Returns a stable function ``celebrate(level)`` that fires a confetti
 * burst scaled to ``level`` and resolves with the preset (so callers
 * can coordinate sustained glows / count-up timing). When the user
 * has ``prefers-reduced-motion`` set the burst is suppressed and the
 * preset is still returned so timing logic stays consistent.
 */
export function useCelebration(): (
  level: CelebrationLevel,
) => Promise<CelebrationPreset> {
  const reducedMotion = useReducedMotion();

  return useCallback(
    async (level: CelebrationLevel) => {
      const preset = PRESETS[level];
      if (typeof window === "undefined" || reducedMotion) return preset;

      // Dynamic import keeps canvas-confetti out of the SSR bundle and
      // out of pages that never celebrate.
      const confettiModule = await import("canvas-confetti");
      const confetti = confettiModule.default;

      // Two-origin burst feels fuller and avoids a single line of
      // particles streaming from one corner. Center burst dominates.
      confetti({
        particleCount: preset.particleCount,
        spread: preset.spread,
        startVelocity: preset.startVelocity,
        ticks: preset.ticks,
        scalar: preset.scalar,
        origin: { x: 0.5, y: 0.4 },
        colors: COLORS,
        disableForReducedMotion: true,
      });

      // Side flares only on big/huge to keep small/medium focused.
      if (level === "big" || level === "huge") {
        const sidesCount = Math.round(preset.particleCount * 0.3);
        confetti({
          particleCount: sidesCount,
          spread: preset.spread,
          startVelocity: preset.startVelocity,
          ticks: preset.ticks,
          scalar: preset.scalar,
          origin: { x: 0, y: 0.6 },
          angle: 60,
          colors: COLORS,
          disableForReducedMotion: true,
        });
        confetti({
          particleCount: sidesCount,
          spread: preset.spread,
          startVelocity: preset.startVelocity,
          ticks: preset.ticks,
          scalar: preset.scalar,
          origin: { x: 1, y: 0.6 },
          angle: 120,
          colors: COLORS,
          disableForReducedMotion: true,
        });
      }

      return preset;
    },
    [reducedMotion],
  );
}

/**
 * Standardised celebration toast copy from the locked emoji-intensity
 * scale. Caller passes the result to ``toast.success(...)``.
 */
export function celebrationCopy(level: CelebrationLevel, label: string): string {
  switch (level) {
    case "small":
      return `${label} 🎉`;
    case "medium":
      return `${label} 🎉🎉`;
    case "big":
      return `${label} 🎉🎉🎉`;
    case "huge":
      return `${label} 🎉🎉🎉🚀`;
  }
}
