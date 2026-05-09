"use client";

/**
 * Per-listing creator dashboard card. Shows status, headline
 * counters, and quick actions (edit / publish / archive / trigger
 * snapshot). Used in /marketplace/me's "My Listings" tab.
 */

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Archive,
  CheckCircle2,
  ChevronRight,
  History,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export interface CreatorListingData {
  id: string;
  title: string;
  description: string;
  price_inr: number;
  status: "draft" | "published" | "suspended" | "archived";
  subscriber_count: number;
  rating_avg: number | null;
  rating_count: number;
  published_at: string | null;
}

interface CreatorDashboardCardProps {
  listing: CreatorListingData;
  onChange: () => void;
}

export function CreatorDashboardCard({
  listing,
  onChange,
}: CreatorDashboardCardProps) {
  const [busy, setBusy] = useState<string | null>(null);

  async function handleAction(
    action: "publish" | "archive" | "snapshot",
  ): Promise<void> {
    setBusy(action);
    try {
      if (action === "publish") {
        await api.post(`/marketplace/listings/${listing.id}/publish`, {});
        toast.success("🎉 Listing publish ho gayi — ab marketplace mein dikhegi");
      } else if (action === "archive") {
        await api.post(`/marketplace/listings/${listing.id}/archive`, {});
        toast.success("Listing archive kar di gayi");
      } else {
        await api.post(
          `/marketplace/listings/${listing.id}/ledger/snapshot/now`,
          {},
        );
        toast.success("🛡️✅ Daily snapshot le liya — chain advance ho gayi");
      }
      onChange();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Action fail ho gaya";
      toast.error(msg);
    } finally {
      setBusy(null);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <header className="flex items-start justify-between gap-3 flex-wrap">
            <div className="space-y-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-sm font-semibold truncate min-w-0">
                  {listing.title}
                </h3>
                <StatusBadge status={listing.status} />
                {listing.price_inr > 0 ? (
                  <Badge className="bg-amber-400/15 text-amber-300 border-amber-300/30 text-[10px]">
                    ₹{listing.price_inr.toLocaleString("en-IN")}
                  </Badge>
                ) : (
                  <Badge className="bg-profit/15 text-profit border-profit/30 text-[10px]">
                    FREE
                  </Badge>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                {listing.description || "No description."}
              </p>
            </div>
            <Link
              href={`/marketplace/${listing.id}`}
              className="text-[11px] text-accent-blue hover:text-accent-blue-hover inline-flex items-center gap-1"
            >
              View public
              <ChevronRight className="h-3 w-3" />
            </Link>
          </header>

          <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
            <span>
              {listing.subscriber_count} subscriber{listing.subscriber_count === 1 ? "" : "s"}
            </span>
            <span>
              {listing.rating_avg == null
                ? "No ratings yet"
                : `${listing.rating_avg.toFixed(1)}★ (${listing.rating_count})`}
            </span>
          </div>

          <div className="flex items-center gap-2 flex-wrap pt-2 border-t border-white/[0.04]">
            {listing.status === "draft" ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAction("publish")}
                disabled={busy != null}
                type="button"
              >
                {busy === "publish" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                )}
                Publish
              </Button>
            ) : null}
            {listing.status !== "archived" ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAction("archive")}
                disabled={busy != null}
                type="button"
              >
                {busy === "archive" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Archive className="h-3.5 w-3.5" />
                )}
                Archive
              </Button>
            ) : null}
            {listing.status === "published" ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAction("snapshot")}
                disabled={busy != null}
                type="button"
              >
                {busy === "snapshot" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <ShieldCheck className="h-3.5 w-3.5" />
                )}
                Trigger Snapshot
              </Button>
            ) : null}
            <Link
              href={`/marketplace/${listing.id}`}
              className="text-[11px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1 ml-auto"
            >
              <History className="h-3 w-3" />
              View ledger
            </Link>
          </div>
        </div>
      </GlassmorphismCard>
    </motion.div>
  );
}

function StatusBadge({ status }: { status: CreatorListingData["status"] }) {
  const palette: Record<CreatorListingData["status"], string> = {
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
