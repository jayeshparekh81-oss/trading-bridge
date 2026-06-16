"use client";

/**
 * /admin — admin dashboard home.
 *
 * Card hub linking the admin subpages + a small ops snapshot from
 * existing endpoints. No new backend.
 */

import Link from "next/link";
import { motion } from "framer-motion";
import {
  Crown,
  Users,
  Megaphone,
  History,
  ShieldAlert,
  Sparkles,
  Scale,
  ArrowUpRight,
  Activity,
} from "lucide-react";
import type { ComponentType } from "react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

interface SystemHealth {
  active_users: number;
  orders_today: number;
  failed_today: number;
  error_rate_pct: number;
  timestamp: string;
}

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

const ADMIN_CARDS: ReadonlyArray<{
  href: string;
  title: string;
  blurb: string;
  icon: ComponentType<{ className?: string }>;
  tone: string;
}> = [
  {
    href: "/admin/users",
    title: "Users",
    blurb: "List + search platform users (read-only).",
    icon: Users,
    tone: "text-accent-blue",
  },
  {
    href: "/admin/announcements",
    title: "Announcements",
    blurb: "Broadcast in-app notification to all active users.",
    icon: Megaphone,
    tone: "text-amber-300",
  },
  {
    href: "/admin/audit",
    title: "Audit logs",
    blurb: "Platform-wide audit trail with action + user filters.",
    icon: History,
    tone: "text-muted-foreground",
  },
  {
    href: "/admin/kill-switch-events",
    title: "Kill-switch events",
    blurb: "Trip timeline across all users + still-active count.",
    icon: ShieldAlert,
    tone: "text-loss",
  },
  {
    href: "/admin/indicators",
    title: "Indicator approval queue",
    blurb: "Pending status-change requests + history.",
    icon: Sparkles,
    tone: "text-accent-blue",
  },
  {
    href: "/admin/compliance",
    title: "Compliance",
    blurb: "Per-strategy + indicator compliance reports.",
    icon: Scale,
    tone: "text-profit",
  },
];

export default function AdminHomePage() {
  const { data: health, isLoading } = useApi<SystemHealth>("/admin/system-health");

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-6"
    >
      <motion.header variants={fadeUp} className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Crown className="h-6 w-6 text-amber-300" /> Admin home
        </h1>
        <p className="text-muted-foreground text-sm">
          Ops dashboard. Cards below jump into each subpage.
        </p>
      </motion.header>

      <motion.section variants={fadeUp}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Snapshot
            label="Active users"
            value={isLoading ? "…" : (health?.active_users ?? 0).toLocaleString()}
            icon={Users}
            tone="text-accent-blue"
          />
          <Snapshot
            label="Orders today"
            value={isLoading ? "…" : (health?.orders_today ?? 0).toLocaleString()}
            icon={Activity}
            tone="text-profit"
          />
          <Snapshot
            label="Failed today"
            value={isLoading ? "…" : (health?.failed_today ?? 0).toLocaleString()}
            icon={ShieldAlert}
            tone={health && health.failed_today > 0 ? "text-loss" : "text-muted-foreground"}
          />
          <Snapshot
            label="Error rate"
            value={isLoading ? "…" : `${health?.error_rate_pct ?? 0}%`}
            icon={Activity}
            tone={health && health.error_rate_pct > 5 ? "text-loss" : "text-muted-foreground"}
          />
        </div>
      </motion.section>

      <motion.section variants={fadeUp} className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          Admin tools
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {ADMIN_CARDS.map((card) => {
            const Icon = card.icon;
            return (
              <Link key={card.href} href={card.href}>
                <GlassmorphismCard className="p-4 h-full group hover:bg-white/[0.03] transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <Icon className={cn("h-5 w-5", card.tone)} />
                    <ArrowUpRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <div className="mt-2">
                    <div className="font-medium">{card.title}</div>
                    <p className="text-xs text-muted-foreground mt-0.5">{card.blurb}</p>
                  </div>
                </GlassmorphismCard>
              </Link>
            );
          })}
        </div>
      </motion.section>
    </motion.div>
  );
}

function Snapshot({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  icon: ComponentType<{ className?: string }>;
  tone: string;
}) {
  return (
    <GlassmorphismCard className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className={cn("text-2xl font-semibold mt-1", tone)}>{value}</div>
        </div>
        <Icon className={cn("h-5 w-5", tone)} />
      </div>
    </GlassmorphismCard>
  );
}
