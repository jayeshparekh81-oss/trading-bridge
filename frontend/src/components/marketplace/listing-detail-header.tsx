"use client";

/**
 * Listing-detail page hero — title, price, creator-id (anonymised),
 * status pill, tags row, subscriber + rating counters. Performance
 * snapshot (cached Trust + Truth + headline backtest stats) is
 * shown when present; null `performance_snapshot` falls back to a
 * "performance data baad mein milega" hint so users don't see a
 * blank box.
 */

import { motion } from "framer-motion";
import { Award, Star, TrendingUp, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { cn } from "@/lib/utils";

export interface ListingDetail {
  id: string;
  title: string;
  description: string;
  price_inr: number;
  tags: string[];
  status: "draft" | "published" | "suspended" | "archived";
  performance_snapshot: Record<string, unknown> | null;
  subscriber_count: number;
  rating_avg: number | null;
  rating_count: number;
  published_at: string | null;
  creator_id: string;
}

interface ListingDetailHeaderProps {
  listing: ListingDetail;
}

function formatPrice(price: number): string {
  if (price <= 0) return "FREE";
  return `₹${price.toLocaleString("en-IN")}`;
}

function getNumeric(snapshot: Record<string, unknown> | null, key: string): number | null {
  if (!snapshot) return null;
  const v = snapshot[key];
  return typeof v === "number" ? v : null;
}

export function ListingDetailHeader({ listing }: ListingDetailHeaderProps) {
  const isPremium = listing.price_inr > 0;
  const trustScore = getNumeric(listing.performance_snapshot, "trust_score");
  const truthScore = getNumeric(listing.performance_snapshot, "truth_score");
  const sevenDayPnl = getNumeric(listing.performance_snapshot, "seven_day_pnl_pct");

  return (
    <motion.div
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <GlassmorphismCard
        hover={false}
        className={cn(
          isPremium ? "border-amber-300/30" : "border-white/[0.06]",
        )}
      >
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="space-y-1.5 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-2xl font-bold leading-tight">
                  {listing.title}
                </h1>
                <StatusBadge status={listing.status} />
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed max-w-2xl">
                {listing.description || "Yeh listing creator ne abhi description nahi diya."}
              </p>
              {listing.tags.length > 0 ? (
                <div className="flex items-center gap-1.5 flex-wrap pt-1">
                  {listing.tags.map((tag) => (
                    <Badge
                      key={tag}
                      className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]"
                    >
                      {tag}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
            <Badge
              className={cn(
                "shrink-0 text-sm uppercase",
                isPremium
                  ? "bg-amber-400/15 text-amber-300 border-amber-300/30"
                  : "bg-profit/15 text-profit border-profit/30",
              )}
            >
              {formatPrice(listing.price_inr)}
            </Badge>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat
              icon={Users}
              label="Subscribers"
              value={listing.subscriber_count}
            />
            <Stat
              icon={Star}
              label="Rating"
              value={listing.rating_avg ?? 0}
              suffix={`/5 (${listing.rating_count})`}
              decimals={1}
            />
            <Stat
              icon={Award}
              label="Trust Score"
              value={trustScore ?? 0}
              suffix={trustScore == null ? "" : "/100"}
              fallback={trustScore == null ? "—" : null}
            />
            <Stat
              icon={TrendingUp}
              label="7-day P&L"
              value={sevenDayPnl ?? 0}
              suffix={sevenDayPnl == null ? "" : "%"}
              fallback={sevenDayPnl == null ? "—" : null}
              decimals={2}
            />
          </div>

          <p className="text-[10px] text-muted-foreground/70 leading-relaxed">
            Creator ID: {anonymiseCreator(listing.creator_id)} ·{" "}
            <span className="text-amber-300/80">L&T Engineer Built</span>
          </p>
          {truthScore != null ? (
            <p className="text-[10px] text-muted-foreground/70 leading-relaxed">
              Truth Score: {truthScore.toFixed(1)} / 100
            </p>
          ) : null}
        </div>
      </GlassmorphismCard>
    </motion.div>
  );
}

function StatusBadge({ status }: { status: ListingDetail["status"] }) {
  const palette: Record<ListingDetail["status"], string> = {
    published: "bg-profit/15 text-profit border-profit/30",
    draft: "bg-white/[0.04] text-muted-foreground border-white/[0.06]",
    suspended: "bg-loss/15 text-loss border-loss/30",
    archived: "bg-muted/15 text-muted-foreground border-muted/30",
  };
  return (
    <Badge className={cn("uppercase text-[10px]", palette[status])}>
      {status}
    </Badge>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  suffix = "",
  decimals = 0,
  fallback = null,
}: {
  icon: typeof Users;
  label: string;
  value: number;
  suffix?: string;
  decimals?: number;
  fallback?: string | null;
}) {
  return (
    <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-2.5 space-y-1">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <div className="text-base font-semibold">
        {fallback ?? (
          <>
            <AnimatedNumber value={value} decimals={decimals} />
            {suffix}
          </>
        )}
      </div>
    </div>
  );
}

function anonymiseCreator(id: string): string {
  return id.length > 12 ? `${id.slice(0, 6)}…${id.slice(-4)}` : id;
}
