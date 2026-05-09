"use client";

/**
 * /marketplace — browse published listings.
 *
 * Reads the public ``GET /api/marketplace/listings`` endpoint with
 * client-side filtering for tag + max-price + min-rating. Phase 1
 * ships a basic ``ORDER BY published_at DESC`` so we sort the same
 * way client-side; Phase 2 polish on the backend will add cursor
 * pagination + trust-weighted ranking.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Filter, Search, Sparkles, Store, UserCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Input } from "@/components/ui/input";
import { useApi } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";
import {
  ListingCard,
  type ListingCardData,
} from "@/components/marketplace/listing-card";

interface ListingsResponse {
  listings: ListingCardData[];
  count: number;
}

const CREATOR_ROLES = new Set(["creator", "admin", "super_admin"]);

export default function MarketplaceBrowsePage() {
  const { user } = useAuth();
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
    const q = search.trim().toLowerCase();
    if (!q) return data.listings;
    return data.listings.filter(
      (l) =>
        l.title.toLowerCase().includes(q) ||
        l.description.toLowerCase().includes(q) ||
        l.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }, [data, search]);

  const isCreator = user?.role != null && CREATOR_ROLES.has(user.role);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-5"
    >
      {/* Header */}
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Store className="h-6 w-6 text-accent-blue" />
            Strategy Marketplace
          </h1>
          <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
            Indian retail traders ke liye verified strategies. Har
            listing ki Strategy Transparency Ledger se 90-day
            forward-test proof milta hai. Browse karo, subscribe
            karo, profitable raho. ✨
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/marketplace/me"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <UserCircle2 className="h-3.5 w-3.5" />
            My Subscriptions
          </Link>
          {isCreator ? (
            <Link href="/marketplace/me?tab=mine">
              <Button variant="outline" size="sm" type="button">
                <Sparkles className="h-3.5 w-3.5" />
                Creator Dashboard
              </Button>
            </Link>
          ) : null}
        </div>
      </header>

      {/* Filters */}
      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-accent-blue" />
            <h3 className="text-sm font-semibold">Filters</h3>
            <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
              {data?.count ?? 0} published
            </Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="space-y-1">
              <label
                htmlFor="search"
                className="text-[10px] uppercase tracking-wide text-muted-foreground"
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
                className="text-[10px] uppercase tracking-wide text-muted-foreground"
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
                className="text-[10px] uppercase tracking-wide text-muted-foreground"
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
                className="text-[10px] uppercase tracking-wide text-muted-foreground"
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

      {/* Grid */}
      {isLoading ? (
        <div className="text-xs text-muted-foreground">Loading marketplace…</div>
      ) : filtered.length === 0 ? (
        <GlassmorphismCard hover={false}>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Aapke filters ke saath koi listing nahi mili. Filters
            adjust karo, ya creators ko encourage karo first listing
            publish karne ke liye.
          </p>
        </GlassmorphismCard>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
      )}
    </motion.div>
  );
}
