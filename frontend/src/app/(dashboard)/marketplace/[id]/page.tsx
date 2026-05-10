"use client";

/**
 * /marketplace/[id] — listing detail.
 *
 * Composes the listing-detail header, the Strategy Transparency
 * Ledger panel (Phase 2), the subscribe button, the ratings
 * list, and the rating-form (subscriber-only). All endpoints are
 * read with the existing useApi hook so the page reactively
 * refreshes after every mutation via ``refetch()``.
 */

import { useMemo, useState } from "react";
import { use } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, MessageSquare, Star } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useApi } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";
import {
  ListingDetailHeader,
  type ListingDetail,
} from "@/components/marketplace/listing-detail-header";
import { TransparencyLedgerPanel } from "@/components/marketplace/transparency-ledger-panel";
import { LedgerHistoryModal } from "@/components/marketplace/ledger-history-modal";
import { SubscribeButton } from "@/components/marketplace/subscribe-button";
import { RatingForm } from "@/components/marketplace/rating-form";

interface SubscriptionRead {
  id: string;
  listing_id: string;
  status: "active" | "cancelled" | "expired";
}

interface SubscriptionListResponse {
  subscriptions: SubscriptionRead[];
  count: number;
}

interface RatingRead {
  id: string;
  listing_id: string;
  rater_id: string;
  rating: number;
  review: string | null;
  created_at: string;
}

interface RatingListResponse {
  ratings: RatingRead[];
  count: number;
}

export default function MarketplaceListingDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: listingId } = use(params);
  const { user } = useAuth();
  const [historyOpen, setHistoryOpen] = useState(false);

  const {
    data: listing,
    isLoading,
    refetch: refetchListing,
  } = useApi<ListingDetail | null>(`/marketplace/listings/${listingId}`, null);

  const { data: subs, refetch: refetchSubs } =
    useApi<SubscriptionListResponse>("/marketplace/subscriptions/me", {
      subscriptions: [],
      count: 0,
    });

  const { data: ratings, refetch: refetchRatings } =
    useApi<RatingListResponse>(
      `/marketplace/listings/${listingId}/ratings?limit=50`,
      { ratings: [], count: 0 },
    );

  const activeSub = useMemo(
    () =>
      subs?.subscriptions.find(
        (s) => s.listing_id === listingId && s.status === "active",
      ) ?? null,
    [subs, listingId],
  );
  const everSubscribed = useMemo(
    () => subs?.subscriptions.some((s) => s.listing_id === listingId) ?? false,
    [subs, listingId],
  );

  const myRating = useMemo(
    () => ratings?.ratings.find((r) => r.rater_id === user?.id) ?? null,
    [ratings, user?.id],
  );

  if (isLoading) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <p className="text-xs text-muted-foreground">Loading listing…</p>
      </div>
    );
  }
  if (listing == null) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-3">
        <Link
          href="/marketplace"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to marketplace
        </Link>
        <GlassmorphismCard hover={false}>
          <p className="text-sm">
            Yeh listing nahi mili — kahin draft toh nahi hai? Public
            view sirf published listings dikhati hai.
          </p>
        </GlassmorphismCard>
      </div>
    );
  }

  const isCreator = user?.id === listing.creator_id;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-5"
    >
      <Link
        href="/marketplace"
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-3 w-3" />
        Back to marketplace
      </Link>

      <ListingDetailHeader listing={listing} />

      {/* Subscribe row */}
      <div className="flex items-center justify-end gap-2">
        <SubscribeButton
          listingId={listing.id}
          priceInr={listing.price_inr}
          isCreator={isCreator}
          isSubscribed={activeSub != null}
          onChange={() => {
            refetchSubs();
            refetchListing();
          }}
        />
      </div>

      <TransparencyLedgerPanel
        listingId={listing.id}
        onOpenHistory={() => setHistoryOpen(true)}
      />

      {/* Rating form (subscribers only) */}
      {everSubscribed && !isCreator ? (
        <RatingForm
          listingId={listing.id}
          existingRating={
            myRating
              ? { id: myRating.id, rating: myRating.rating, review: myRating.review }
              : null
          }
          onSubmitted={() => {
            refetchRatings();
            refetchListing();
          }}
        />
      ) : null}

      {/* Ratings list */}
      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <header className="flex items-center justify-between">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-accent-blue" />
              Subscriber Reviews
            </h2>
            <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
              {ratings?.count ?? 0} total
            </Badge>
          </header>
          {ratings && ratings.count > 0 ? (
            <div className="space-y-2">
              {ratings.ratings.map((r) => (
                <ReviewRow key={r.id} review={r} />
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Pehla review aapka ho sakta hai — subscribe karo aur
              feedback do.
            </p>
          )}
        </div>
      </GlassmorphismCard>

      <LedgerHistoryModal
        listingId={listing.id}
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
      />
    </motion.div>
  );
}

function ReviewRow({ review }: { review: RatingRead }) {
  return (
    <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-3 space-y-1.5">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-0.5">
          {[1, 2, 3, 4, 5].map((n) => (
            <Star
              key={n}
              className={
                n <= review.rating
                  ? "h-3.5 w-3.5 fill-amber-300 text-amber-300"
                  : "h-3.5 w-3.5 text-muted-foreground/40"
              }
            />
          ))}
        </div>
        <span className="text-[10px] text-muted-foreground">
          by {review.rater_id.slice(0, 8)}…
        </span>
        <span className="text-[10px] text-muted-foreground/70 ml-auto">
          {new Date(review.created_at).toLocaleDateString("en-IN")}
        </span>
      </div>
      {review.review ? (
        <p className="text-[12px] text-foreground/90 leading-relaxed">
          {review.review}
        </p>
      ) : (
        <p className="text-[10px] text-muted-foreground/70 italic">
          No written review.
        </p>
      )}
    </div>
  );
}
