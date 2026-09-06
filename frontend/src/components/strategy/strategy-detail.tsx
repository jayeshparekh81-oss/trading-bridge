"use client";

/**
 * In-app strategy detail: the SAME StrategyCard the public Track Record shows
 * (full layout, joined to the marketplace listing), then the things only the
 * app can do — Subscribe, the transparency ledger, ratings.
 */

import { useState } from "react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { MessageSquare, Star } from "lucide-react";
import { StrategyCard, unprovenItem, type StrategyListingInfo } from "@/components/strategy/strategy-card";
import { TransparencyLedgerPanel } from "@/components/marketplace/transparency-ledger-panel";
import { LedgerHistoryModal } from "@/components/marketplace/ledger-history-modal";
import { SubscribeButton, type SubscriptionStatus } from "@/components/marketplace/subscribe-button";
import { RatingForm } from "@/components/marketplace/rating-form";
import type { LiveRecord, ShowcaseDetail, ShowcaseListItem } from "@/lib/showcase/data";

export interface ListingDetail {
  id: string;
  creator_id: string;
  title: string;
  description: string;
  price_inr: number;
  tags: string[];
  status: string;
  subscriber_count: number;
  rating_avg: number | null;
  rating_count: number;
  published_at: string | null;
  performance_snapshot: Record<string, unknown> | null;
}

export interface RatingRead {
  id: string;
  listing_id: string;
  rater_id: string;
  rating: number;
  review: string | null;
  created_at: string;
}

export interface StrategyDetailProps {
  listing: ListingDetail;
  /** The showcase entry this listing is joined to (null = no published proof yet). */
  showcase: { item: ShowcaseListItem; detail: ShowcaseDetail | null; live: LiveRecord | null } | null;
  /** The showcase index is still loading — do not call the listing unproven yet. */
  showcaseLoading?: boolean;
  isCreator: boolean;
  subscriptionStatus: SubscriptionStatus;
  everSubscribed: boolean;
  myRating: RatingRead | null;
  ratings: { ratings: RatingRead[]; count: number } | null;
  onSubscriptionChange: () => void;
  onRated: () => void;
}

export function StrategyDetail(p: StrategyDetailProps) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const listingInfo: StrategyListingInfo = {
    id: p.listing.id,
    price_inr: p.listing.price_inr,
    subscriber_count: p.listing.subscriber_count,
    rating_avg: p.listing.rating_avg,
    rating_count: p.listing.rating_count,
  };
  return (
    <div className="space-y-5" data-testid="strategy-detail">
      <StrategyCard
        item={p.showcase?.item ?? unprovenItem(p.listing.id, p.listing.title)}
        detail={p.showcase?.detail ?? null}
        live={p.showcase?.live ?? null}
        listing={listingInfo}
        surface="app"
        layout="full"
        unproven={!p.showcase && !p.showcaseLoading}
        cta={
          <div className="mt-3.5 flex flex-col items-start gap-1.5" data-testid="strategy-subscribe-row">
            <SubscribeButton listingId={p.listing.id} priceInr={p.listing.price_inr} isCreator={p.isCreator} subscriptionStatus={p.subscriptionStatus} onChange={p.onSubscriptionChange} />
            {!p.isCreator && p.listing.price_inr > 0 ? (
              <p className="text-10 text-muted-foreground max-w-md leading-relaxed">
                Subscription unlocks access + sizing controls. Execution stays <span className="text-foreground">seekhne wala mode (simulated)</span> until live trading is enabled for subscribers — it is not yet. Past performance does not guarantee future results.
              </p>
            ) : null}
          </div>
        }
      />

      {p.listing.description ? (
        <GlassmorphismCard hover={false}>
          <p className="text-sm text-muted-foreground leading-relaxed" data-testid="strategy-description">
            {p.listing.description}
          </p>
        </GlassmorphismCard>
      ) : null}

      <TransparencyLedgerPanel listingId={p.listing.id} onOpenHistory={() => setHistoryOpen(true)} />
      <LedgerHistoryModal listingId={p.listing.id} open={historyOpen} onClose={() => setHistoryOpen(false)} />

      {p.everSubscribed && !p.isCreator ? (
        <RatingForm listingId={p.listing.id} existingRating={p.myRating ? { id: p.myRating.id, rating: p.myRating.rating, review: p.myRating.review } : null} onSubmitted={p.onRated} />
      ) : null}

      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <header className="flex items-center justify-between">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-accent-blue" />
              Subscriber Reviews
            </h2>
            <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-10">{p.ratings?.count ?? 0} total</Badge>
          </header>
          {p.ratings && p.ratings.count > 0 ? (
            <div className="space-y-2">
              {p.ratings.ratings.map((r) => (
                <div key={r.id} className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                  <div className="flex items-center gap-1 text-amber-300 text-xs">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star key={i} className={i < r.rating ? "h-3 w-3 fill-current" : "h-3 w-3 opacity-30"} />
                    ))}
                    <span className="ml-2 text-10 text-muted-foreground">{new Date(r.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>
                  </div>
                  {r.review ? <p className="mt-1 text-xs text-foreground/85">{r.review}</p> : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-11 text-muted-foreground leading-relaxed">Pehla review aapka ho sakta hai — subscribe karo aur feedback do.</p>
          )}
        </div>
      </GlassmorphismCard>
    </div>
  );
}
