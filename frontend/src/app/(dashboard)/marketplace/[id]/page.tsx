"use client";

/**
 * /marketplace/[id] — strategy detail INSIDE the app (the whole shop).
 *
 * Renders <StrategyDetail>: the SAME StrategyCard the public Track Record
 * shows (joined to this listing by the showcase live record's listing_id),
 * plus Subscribe, the transparency ledger and ratings — the parts only the
 * app has. Data: hooks/useShowcase.ts + the marketplace endpoints.
 */

import { useMemo } from "react";
import { use } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { useApi } from "@/shared/api/use-api";
import { useAuth } from "@/lib/auth";
import { useShowcaseIndex, useStrategyCardData } from "@/hooks/useShowcase";
import { StrategyDetail, type ListingDetail, type RatingRead } from "@/components/strategy/strategy-detail";

interface SubscriptionRead {
  id: string;
  listing_id: string;
  status: "pending" | "active" | "cancelled" | "expired" | "past_due";
}

interface SubscriptionListResponse {
  subscriptions: SubscriptionRead[];
  count: number;
}

interface RatingListResponse {
  ratings: RatingRead[];
  count: number;
}

export default function MarketplaceListingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: listingId } = use(params);
  const { user } = useAuth();

  const { data: listing, isLoading, refetch: refetchListing } = useApi<ListingDetail | null>(`/marketplace/listings/${listingId}`, null);
  const { data: subs, refetch: refetchSubs } = useApi<SubscriptionListResponse>("/marketplace/subscriptions/me", { subscriptions: [], count: 0 });
  const { data: ratings, refetch: refetchRatings } = useApi<RatingListResponse>(`/marketplace/listings/${listingId}/ratings?limit=50`, { ratings: [], count: 0 });

  // The ONE data source for the proof numbers — same hook as the public page.
  const index = useShowcaseIndex();
  const entry = index.byListingId[listingId] ?? null;
  const feed = useStrategyCardData(entry?.item.key ?? null);

  // Resting subscribe state for this listing: active (manage), pending
  // (awaiting payment confirmation), or null (show CTA). Active wins over a
  // stale pending row if both somehow exist.
  const subStatus = useMemo<"active" | "pending" | null>(() => {
    const rows = subs?.subscriptions.filter((s) => s.listing_id === listingId) ?? [];
    if (rows.some((s) => s.status === "active")) return "active";
    if (rows.some((s) => s.status === "pending")) return "pending";
    return null;
  }, [subs, listingId]);
  const everSubscribed = useMemo(() => subs?.subscriptions.some((s) => s.listing_id === listingId) ?? false, [subs, listingId]);
  const myRating = useMemo(() => ratings?.ratings.find((r) => r.rater_id === user?.id) ?? null, [ratings, user?.id]);

  if (isLoading) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <p className="text-xs text-muted-foreground">Loading strategy…</p>
      </div>
    );
  }
  if (listing == null) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-3">
        <Link href="/marketplace" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-3 w-3" />
          Back to marketplace
        </Link>
        <GlassmorphismCard hover={false}>
          <p className="text-sm">Yeh strategy nahi mili — kahin draft toh nahi hai? Sirf published strategies dikhti hain.</p>
        </GlassmorphismCard>
      </div>
    );
  }

  const isCreator = user?.id === listing.creator_id;

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }} className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-5">
      <Link href="/marketplace" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors" data-testid="detail-back">
        <ArrowLeft className="h-3 w-3" />
        Back to marketplace
      </Link>

      <StrategyDetail
        listing={listing}
        showcase={entry ? { item: entry.item, detail: feed.detail, live: feed.live ?? entry.live } : null}
        showcaseLoading={index.loading}
        isCreator={isCreator}
        subscriptionStatus={subStatus}
        everSubscribed={everSubscribed}
        myRating={myRating}
        ratings={ratings}
        onSubscriptionChange={() => {
          refetchSubs();
          refetchListing();
        }}
        onRated={() => {
          refetchRatings();
          refetchListing();
        }}
      />
    </motion.div>
  );
}
