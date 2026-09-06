"use client";

/**
 * /marketplace — the shop, inside the app.
 *
 * ONE card (components/strategy/strategy-card.tsx) fed by ONE data source
 * (hooks/useShowcase.ts), the same as the public Track Record:
 *   Simple  → "Strategy chuno": one rich card at a time, big, Pichla/Agla,
 *             Subscribe right on the card (components/simple/strategy-pick.tsx).
 *   Pro     → filters + the grid of compact cards; "Dekho" opens the detail.
 * Listings the showcase does not know about render the same card honestly
 * empty (`unproven`) — never a bare card, never a fabricated zero.
 *
 * Reads the public ``GET /api/marketplace/listings`` endpoint with
 * client-side filtering for tag + max-price + min-rating.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Filter, Search, Sparkles } from "lucide-react";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { Input } from "@/shared/ui/input";
import { ProPage, ProEmpty } from "@/components/dashboard/pro-page";
import { useApi } from "@/shared/api/use-api";
import { useAuth } from "@/lib/auth";
import { useLadderOptional } from "@/hooks/useLadder";
import { useShowcaseIndex } from "@/hooks/useShowcase";
import { orderForShop } from "@/lib/marketplace/order-for-shop";
import { ListingStrategyCard, SimpleStrategyPick, type MarketplaceListing } from "@/components/simple/strategy-pick";

interface ListingsResponse {
  listings: MarketplaceListing[];
  count: number;
}

const CREATOR_ROLES = new Set(["creator", "admin", "super_admin"]);

export default function MarketplaceBrowsePage() {
  const { user } = useAuth();
  const ladder = useLadderOptional();
  const simple = (ladder?.level ?? 4) < 4;
  // The ONE data source for the proof numbers — same hook as the public Proof page.
  const index = useShowcaseIndex();
  const [search, setSearch] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [maxPriceFilter, setMaxPriceFilter] = useState("");
  const [minRatingFilter, setMinRatingFilter] = useState("");

  const queryParts: string[] = [];
  if (tagFilter.trim()) queryParts.push(`tag=${encodeURIComponent(tagFilter.trim())}`);
  if (maxPriceFilter.trim() && !Number.isNaN(Number(maxPriceFilter)))
    queryParts.push(`max_price=${maxPriceFilter}`);
  if (minRatingFilter.trim() && !Number.isNaN(Number(minRatingFilter)))
    queryParts.push(`min_rating=${minRatingFilter}`);
  const url = `/marketplace/listings${queryParts.length ? `?${queryParts.join("&")}` : ""}`;

  const { data, isLoading } = useApi<ListingsResponse>(url, {
    listings: [],
    count: 0,
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = simple ? "" : search.trim().toLowerCase();
    if (!q) return data.listings;
    return data.listings.filter(
      (l) =>
        l.title.toLowerCase().includes(q) ||
        l.description.toLowerCase().includes(q) ||
        l.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }, [data, search, simple]);

  const isCreator = user?.role != null && CREATOR_ROLES.has(user.role);

  const hasFilters = Boolean(
    search.trim() ||
      tagFilter.trim() ||
      maxPriceFilter.trim() ||
      minRatingFilter.trim(),
  );

  // Simple mode: one big card at a time — no filters, plain words, Wapas from the shell.
  if (simple) return <SimpleStrategyPick listings={filtered} index={index} loading={isLoading} />;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto"
    >
      {/* No primary action: browsing IS this page, and "My Strategies" is
          already one tap away in the sidebar. A top-right button repeating a
          sidebar entry is a second door to the same room. */}
      <ProPage>
        {/* Filters */}
        <GlassmorphismCard hover={false}>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-accent-blue" />
              <h3 className="text-sm font-semibold">Filters</h3>
              <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06] text-10">
                {data?.count ?? 0} published
              </Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="space-y-1">
                <label
                  htmlFor="search"
                  className="text-10 uppercase tracking-wide text-muted-foreground"
                >
                  Search
                </label>
                <div className="relative">
                  <Search className="h-3.5 w-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <Input
                    id="search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="title / tag / description"
                    className="pl-8"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <label
                  htmlFor="tag"
                  className="text-10 uppercase tracking-wide text-muted-foreground"
                >
                  Tag
                </label>
                <Input
                  id="tag"
                  value={tagFilter}
                  onChange={(e) => setTagFilter(e.target.value)}
                  placeholder="intraday / swing / options"
                />
              </div>
              <div className="space-y-1">
                <label
                  htmlFor="max-price"
                  className="text-10 uppercase tracking-wide text-muted-foreground"
                >
                  Max Price (₹)
                </label>
                <Input
                  id="max-price"
                  type="number"
                  min={0}
                  value={maxPriceFilter}
                  onChange={(e) => setMaxPriceFilter(e.target.value)}
                  placeholder="0 = free only"
                />
              </div>
              <div className="space-y-1">
                <label
                  htmlFor="min-rating"
                  className="text-10 uppercase tracking-wide text-muted-foreground"
                >
                  Min Rating
                </label>
                <Input
                  id="min-rating"
                  type="number"
                  min={0}
                  max={5}
                  step={0.1}
                  value={minRatingFilter}
                  onChange={(e) => setMinRatingFilter(e.target.value)}
                  placeholder="0-5"
                />
              </div>
            </div>
          </div>
        </GlassmorphismCard>

        {/* Creator's own listings live on My Strategies → My Listings. It is not
            the primary action of the browse page, so it sits with the content. */}
        {isCreator ? (
          <div className="flex justify-end">
            <Link href="/marketplace/me?tab=mine">
              <Button variant="outline" size="sm" type="button">
                <Sparkles className="h-3.5 w-3.5" />
                My Listings
              </Button>
            </Link>
          </div>
        ) : null}

        {/* Grid */}
        {isLoading ? (
          <div className="text-xs text-muted-foreground">Loading marketplace…</div>
        ) : filtered.length === 0 ? (
          hasFilters ? (
            <ProEmpty
              headline="In filters ke saath koi strategy nahi mili"
              next="Filters halke karo — search, tag, max price ya min rating khaali kar ke phir dekho."
            />
          ) : (
            <ProEmpty
              headline="Abhi marketplace mein koi strategy nahi hai"
              next="Creators jaise hi publish karenge, listings yahan aa jayengi. Tab tak apni khud ki strategy bana ke chala sakte ho."
              action={{ label: "Nayi strategy", href: "/strategies/new" }}
            />
          )
        ) : (
          /* The same card the public Proof page shows, compact; proof-backed listings first. */
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="pro-marketplace-grid">
            {orderForShop(filtered, index.byListingId).map((listing) => (
              <ListingStrategyCard key={listing.id} listing={listing} entry={index.byListingId[listing.id] ?? null} indexLoading={index.loading} layout="compact" />
            ))}
          </div>
        )}
      </ProPage>
    </motion.div>
  );
}
