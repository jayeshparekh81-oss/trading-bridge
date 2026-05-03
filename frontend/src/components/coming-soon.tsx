"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";

interface ComingSoonProps {
  pageName: string;
  description: string;
  /** Optional: e.g. "Tier 2 — next sprint". Renders below description. */
  eta?: string;
}

/**
 * Placeholder for routes that exist in the sidebar but aren't yet wired
 * to real backend. Replaces the mock-data UIs so the customer never sees
 * misleading data. Keep a single visual treatment so the pattern is
 * immediately recognisable across all unwired pages.
 *
 * Pages currently using this:
 *   /brokers, /strategies, /webhooks, /alerts, /analytics, /settings,
 *   /admin, /admin/users, /admin/audit, /admin/kill-switch-events,
 *   /admin/announcements
 *
 * Wire-up tracked in docs/FRONTEND_NEXT_SPRINT.md.
 */
export function ComingSoon({ pageName, description, eta }: ComingSoonProps) {
  return (
    <div className="p-4 md:p-6 lg:p-8">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="max-w-xl mx-auto"
      >
        <GlassmorphismCard hover={false}>
          <div className="flex flex-col items-center text-center py-10 px-4">
            <div className="text-6xl mb-4" aria-hidden>🚧</div>
            <h1 className="text-2xl font-bold mb-2">{pageName} — coming soon</h1>
            <p className="text-muted-foreground max-w-md leading-relaxed">
              {description}
            </p>
            <p className="text-xs text-muted-foreground mt-6">
              {eta ?? "Wire-up scheduled in next sprint."}
            </p>
            <div className="flex gap-2 mt-6">
              <Link href="/">
                <GlowButton size="sm" variant="primary">Back to overview</GlowButton>
              </Link>
              <Link href="/positions">
                <GlowButton size="sm">Live positions</GlowButton>
              </Link>
            </div>
          </div>
        </GlassmorphismCard>
      </motion.div>
    </div>
  );
}
