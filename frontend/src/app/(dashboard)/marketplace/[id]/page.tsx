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
import { AlertTriangle, ArrowLeft } from "lucide-react";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { GlowButton } from "@/shared/ui/glow-button";
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

  const { data: listing, isLoading, error: listingError, refetch: refetchListing } = useApi<ListingDetail | null>(`/marketplace/listings/${listingId}`, null);
  const { data: subs, error: subsError, refetch: refetchSubs } = useApi<SubscriptionListResponse>("/marketplace/subscriptions/me", { subscriptions: [], count: 0 });
  const { data: ratings, error: ratingsError, refetch: refetchRatings } = useApi<RatingListResponse>(`/marketplace/listings/${listingId}/ratings?limit=50`, { ratings: [], count: 0 });

  // Two very different things used to render the same sentence.
  //
  //   "Yeh strategy nahi mili"  is an ANSWER — the backend replied 404
  //                             ("Listing not found.") because the listing is
  //                             absent or is someone else's draft.
  //   a failed fetch            is SILENCE — network down, 500, session gone.
  //                             We do not know whether the listing exists.
  //
  // Saying "nahi mili" on silence is a false claim about the shop. So the
  // not-found copy is spoken ONLY for the 404 answer; anything we cannot
  // recognise as that answer is treated as a load failure. That is the safe
  // direction to be wrong in — we never announce an absence we did not hear.
  const listingMissing = listing == null && (listingError == null || /not found/i.test(listingError));
  const listingUnreachable = listing == null && listingError != null && !listingMissing;

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
  if (listingUnreachable) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-3">
        <Link href="/marketplace" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-3 w-3" />
          Back to marketplace
        </Link>
        <GlassmorphismCard hover={false}>
          <div className="space-y-2">
            <p className="text-sm font-medium flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-loss" />
              Yeh strategy load nahi ho payi
            </p>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Iska matlab yeh nahi ki strategy hai hi nahi — abhi hum ise laa nahi paye. Ek baar dobara koshish karo.
            </p>
            <p className="text-11 text-muted-foreground">{listingError}</p>
            <GlowButton size="sm" className="mt-1" onClick={refetchListing} data-testid="detail-retry">
              Dobara koshish karo
            </GlowButton>
          </div>
        </GlassmorphismCard>
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

      {/* The subscription and ratings fetches carry EMPTY fallbacks, so a
          failure reads exactly like "you have no subscription" and "no reviews
          yet". Both are claims we cannot make when the request never landed —
          the second one costs a customer money if he pays for what he already
          has. Say what we do not know, and offer the retry. */}
      {subsError || ratingsError ? (
        <GlassmorphismCard hover={false}>
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-loss shrink-0 mt-0.5" />
            <div className="space-y-1.5">
              <p className="text-xs font-medium">Is page ka kuch hissa load nahi ho paya</p>
              {subsError ? (
                <p className="text-11 text-muted-foreground leading-relaxed">
                  Aapki subscription status nahi mili. Neeche Subscribe dikh sakta hai — iska matlab yeh
                  nahi ki aapne subscribe nahi kiya hua. Paise dene se pehle ek baar dobara koshish karo.
                </p>
              ) : null}
              {ratingsError ? (
                <p className="text-11 text-muted-foreground leading-relaxed">
                  Reviews nahi aaye — neeche jo khaali dikh raha hai woh &ldquo;koi review nahi hai&rdquo;
                  nahi hai, bas abhi mil nahi paya.
                </p>
              ) : null}
              <GlowButton
                size="sm"
                className="mt-1"
                data-testid="detail-side-retry"
                onClick={() => {
                  if (subsError) refetchSubs();
                  if (ratingsError) refetchRatings();
                }}
              >
                Dobara koshish karo
              </GlowButton>
            </div>
          </div>
        </GlassmorphismCard>
      ) : null}

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
