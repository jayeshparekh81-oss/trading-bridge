"use client";

/**
 * Simple mode's "Strategy chuno": ONE rich strategy card at a time, big,
 * with Pichla/Agla and Subscribe right on the card. It is the SAME
 * <StrategyCard> the public Track Record and the Pro grid render
 * (components/strategy/strategy-card.tsx) from the SAME data
 * (hooks/useShowcase.ts). ListingStrategyCard is the one listing→card adapter
 * both the Simple picker and the Pro grid use.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useApi } from "@/lib/use-api";
import { useLanguage } from "@/contexts/LanguageContext";
import { t } from "@/lib/simple/copy";
import { useStrategyCardData, type ShowcaseIndex, type ShowcaseIndexEntry } from "@/hooks/useShowcase";
import { StrategyCard, unprovenItem } from "@/components/strategy/strategy-card";
import { orderForShop } from "@/lib/marketplace/order-for-shop";
import { SubscribeButton } from "@/components/marketplace/subscribe-button";

export interface MarketplaceListing {
  id: string;
  title: string;
  description: string;
  price_inr: number;
  tags: string[];
  status: string;
  subscriber_count: number;
  rating_avg: number | null;
  rating_count: number;
  published_at: string | null;
}

interface SubscriptionRead {
  id: string;
  listing_id: string;
  status: string;
}

interface SubscriptionListResponse {
  subscriptions: SubscriptionRead[];
  count: number;
}

/** One listing → the shared card. Fetches the listing's proof (detail + live) itself. */
export function ListingStrategyCard({
  listing,
  entry,
  indexLoading,
  layout,
  cta,
}: {
  listing: MarketplaceListing;
  entry: ShowcaseIndexEntry | null;
  indexLoading: boolean;
  layout: "full" | "compact";
  cta?: React.ReactNode;
}) {
  const feed = useStrategyCardData(entry?.item.key ?? null);
  const info = {
    id: listing.id,
    price_inr: listing.price_inr,
    subscriber_count: listing.subscriber_count,
    rating_avg: listing.rating_avg,
    rating_count: listing.rating_count,
  };
  if (!entry) {
    return (
      <StrategyCard
        item={unprovenItem(listing.id, listing.title)}
        listing={info}
        surface="app"
        layout={layout}
        unproven={!indexLoading}
        cta={cta}
        href={`/marketplace/${listing.id}`}
      />
    );
  }
  return (
    <StrategyCard
      item={entry.item}
      detail={feed.detail}
      live={feed.live ?? entry.live}
      listing={info}
      surface="app"
      layout={layout}
      cta={cta}
      href={`/marketplace/${listing.id}`}
    />
  );
}


export function SimpleStrategyPick({ listings, index, loading }: { listings: MarketplaceListing[]; index: ShowcaseIndex; loading: boolean }) {
  const { lang } = useLanguage();
  const [i, setI] = useState(0);
  const { data: subs, refetch: refetchSubs } = useApi<SubscriptionListResponse>("/marketplace/subscriptions/me", { subscriptions: [], count: 0 });
  const ordered = useMemo(() => orderForShop(listings, index.byListingId), [listings, index.byListingId]);
  const cur = ordered[Math.min(i, Math.max(0, ordered.length - 1))];

  const subStatus = (id: string): "active" | "pending" | null => {
    const rows = subs?.subscriptions.filter((s) => s.listing_id === id) ?? [];
    if (rows.some((s) => s.status === "active")) return "active";
    if (rows.some((s) => s.status === "pending")) return "pending";
    return null;
  };

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto space-y-4" data-testid="simple-strategy-pick">
      <header>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="simple-pick-title">{t(lang, "tile_strategy")}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t(lang, "tile_strategy_sub")}</p>
      </header>

      {loading && ordered.length === 0 ? (
        <p className="text-sm text-muted-foreground">Dekh rahe hain…</p>
      ) : ordered.length === 0 ? (
        <GlassmorphismCard hover={false} data-testid="simple-pick-empty">
          <p className="text-sm leading-relaxed">Abhi koi taiyar strategy nahi hai. Jab aayegi, yahan dikhegi — tab tak Ghar par signals dekho.</p>
        </GlassmorphismCard>
      ) : (
        <>
          <ListingStrategyCard
            key={cur.id}
            listing={cur}
            entry={index.byListingId[cur.id] ?? null}
            indexLoading={index.loading}
            layout="full"
            cta={
              <div className="mt-3.5 flex flex-wrap items-center gap-3" data-testid="simple-pick-cta">
                <SubscribeButton listingId={cur.id} priceInr={cur.price_inr} isCreator={false} subscriptionStatus={subStatus(cur.id)} onChange={refetchSubs} />
                <Link href={`/marketplace/${cur.id}`} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground" data-testid="simple-pick-more">
                  Aur jaano <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            }
          />
          {ordered.length > 1 ? (
            <div className="flex items-center justify-between gap-3" data-testid="simple-pick-pager">
              <Button variant="outline" size="sm" type="button" disabled={i <= 0} onClick={() => setI((n) => Math.max(0, n - 1))} data-testid="simple-pick-prev">
                <ChevronLeft className="h-4 w-4" /> Pichla
              </Button>
              <span className="text-xs text-muted-foreground" data-testid="simple-pick-count">
                {Math.min(i, ordered.length - 1) + 1} / {ordered.length}
              </span>
              <Button variant="outline" size="sm" type="button" disabled={i >= ordered.length - 1} onClick={() => setI((n) => Math.min(ordered.length - 1, n + 1))} data-testid="simple-pick-next">
                Agla <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
