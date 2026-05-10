"use client";

/**
 * Browse-grid card. Click navigates to the listing detail page.
 * Shows title, creator-anonymised id, price (FREE / ₹X), tag chips,
 * subscriber count + rating average. Hover halo for affordance.
 */

import Link from "next/link";
import { motion } from "framer-motion";
import { Star, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";

export interface ListingCardData {
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

interface ListingCardProps {
  listing: ListingCardData;
}

function formatPrice(price: number): string {
  if (price <= 0) return "FREE";
  return `₹${price.toLocaleString("en-IN")}`;
}

export function ListingCard({ listing }: ListingCardProps) {
  const isPremium = listing.price_inr > 0;
  return (
    <Link href={`/marketplace/${listing.id}`} className="block">
      <motion.div
        whileHover={{ y: -2 }}
        whileTap={{ scale: 0.99 }}
        transition={{ type: "spring", stiffness: 400, damping: 25 }}
      >
        <GlassmorphismCard
          hover={false}
          className={cn(
            "h-full transition-colors",
            isPremium
              ? "border-amber-400/30 hover:border-amber-300/50"
              : "hover:border-accent-blue/40",
          )}
        >
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-base font-semibold leading-tight line-clamp-2">
                {listing.title}
              </h3>
              <Badge
                className={cn(
                  "shrink-0 text-[10px] uppercase",
                  isPremium
                    ? "bg-amber-400/15 text-amber-300 border-amber-300/30"
                    : "bg-profit/15 text-profit border-profit/30",
                )}
              >
                {formatPrice(listing.price_inr)}
              </Badge>
            </div>

            {listing.description ? (
              <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-3">
                {listing.description}
              </p>
            ) : null}

            {listing.tags.length > 0 ? (
              <div className="flex items-center gap-1 flex-wrap">
                {listing.tags.slice(0, 3).map((tag) => (
                  <Badge
                    key={tag}
                    className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]"
                  >
                    {tag}
                  </Badge>
                ))}
                {listing.tags.length > 3 ? (
                  <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
                    +{listing.tags.length - 3}
                  </Badge>
                ) : null}
              </div>
            ) : null}

            <div className="flex items-center gap-3 pt-1 border-t border-white/[0.04] text-[11px] text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Users className="h-3 w-3" />
                {listing.subscriber_count}
              </span>
              {listing.rating_avg != null ? (
                <span className="inline-flex items-center gap-1">
                  <Star className="h-3 w-3 text-amber-300" />
                  {listing.rating_avg.toFixed(1)}{" "}
                  <span className="text-muted-foreground/70">
                    ({listing.rating_count})
                  </span>
                </span>
              ) : (
                <span className="text-muted-foreground/60">No ratings yet</span>
              )}
            </div>
          </div>
        </GlassmorphismCard>
      </motion.div>
    </Link>
  );
}
