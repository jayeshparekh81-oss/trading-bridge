"use client";

/**
 * /marketplace/me — user's own marketplace surface.
 *
 * Two tabs:
 *   * Subscriptions — every listing the user has subscribed to
 *     (active + cancelled + expired). Cancelled rows stick around
 *     because the rating endpoint accepts ex-subscribers as raters.
 *   * My Listings   — creator-only. Renders one
 *     CreatorDashboardCard per listing across all statuses.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ChevronRight,
  Sparkles,
  UserCircle2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useApi } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import {
  CreatorDashboardCard,
  type CreatorListingData,
} from "@/components/marketplace/creator-dashboard-card";

interface SubscriptionRead {
  id: string;
  listing_id: string;
  subscribed_at: string;
  access_until: string | null;
  status: "active" | "cancelled" | "expired";
  amount_paid_inr: number;
}

interface SubscriptionListResponse {
  subscriptions: SubscriptionRead[];
  count: number;
}

interface CreatorListingResponse {
  listings: CreatorListingData[];
  count: number;
}

const CREATOR_ROLES = new Set(["creator", "admin", "super_admin"]);

type Tab = "subs" | "mine";

export default function MarketplaceMePage() {
  const { user } = useAuth();
  const isCreator = user?.role != null && CREATOR_ROLES.has(user.role);

  // Initial-tab sync from the ``?tab=mine`` query param so the
  // creator-dashboard CTA on the browse page lands users in the
  // right tab. Reading via ``useSearchParams`` keeps this
  // SSR-safe and avoids the ``setState-in-effect`` lint error.
  const searchParams = useSearchParams();
  const initialTab: Tab =
    isCreator && searchParams?.get("tab") === "mine" ? "mine" : "subs";
  const [tab, setTab] = useState<Tab>(initialTab);

  const { data: subs, refetch: refetchSubs } =
    useApi<SubscriptionListResponse>("/marketplace/subscriptions/me", {
      subscriptions: [],
      count: 0,
    });

  const { data: mine, refetch: refetchMine } = useApi<CreatorListingResponse>(
    isCreator && tab === "mine" ? "/marketplace/listings/me" : null,
    { listings: [], count: 0 },
  );

  const groupedSubs = useMemo(() => {
    const active: SubscriptionRead[] = [];
    const inactive: SubscriptionRead[] = [];
    for (const s of subs?.subscriptions ?? []) {
      (s.status === "active" ? active : inactive).push(s);
    }
    return { active, inactive };
  }, [subs]);

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

      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <UserCircle2 className="h-6 w-6 text-accent-blue" />
          My Marketplace
        </h1>
        <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
          Apni subscriptions track karo. Creators yahan se apni
          listings manage karte hain — publish, archive, ya daily
          ledger snapshot trigger karo.
        </p>
      </header>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-white/[0.04]">
        <TabButton
          active={tab === "subs"}
          onClick={() => setTab("subs")}
          label="Subscriptions"
          count={subs?.count ?? 0}
        />
        {isCreator ? (
          <TabButton
            active={tab === "mine"}
            onClick={() => setTab("mine")}
            label="My Listings"
            count={mine?.count ?? 0}
          />
        ) : null}
      </div>

      {tab === "subs" ? (
        <SubscriptionsView
          subs={groupedSubs}
          totalCount={subs?.count ?? 0}
          onRefresh={refetchSubs}
        />
      ) : (
        <MyListingsView
          listings={mine?.listings ?? []}
          isCreator={isCreator}
          onRefresh={refetchMine}
        />
      )}
    </motion.div>
  );
}

function TabButton({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
        active
          ? "border-accent-blue text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {label}{" "}
      <span className="text-[10px] text-muted-foreground/70">({count})</span>
    </button>
  );
}

function SubscriptionsView({
  subs,
  totalCount,
  onRefresh,
}: {
  subs: { active: SubscriptionRead[]; inactive: SubscriptionRead[] };
  totalCount: number;
  onRefresh: () => void;
}) {
  if (totalCount === 0) {
    return (
      <GlassmorphismCard hover={false}>
        <p className="text-sm leading-relaxed">
          Aapne abhi tak kisi listing ko subscribe nahi kiya. Browse
          karo aur kuch interesting milta hai toh subscribe karo.
        </p>
      </GlassmorphismCard>
    );
  }
  return (
    <div className="space-y-4">
      {subs.active.length > 0 ? (
        <SubGroup title="Active" subs={subs.active} />
      ) : null}
      {subs.inactive.length > 0 ? (
        <SubGroup title="Past" subs={subs.inactive} />
      ) : null}
      <button
        type="button"
        onClick={onRefresh}
        className="hidden"
        aria-hidden
      />
    </div>
  );
}

function SubGroup({ title, subs }: { title: string; subs: SubscriptionRead[] }) {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-accent-purple" />
        {title}
      </h2>
      <div className="space-y-2">
        {subs.map((sub) => (
          <Link
            key={sub.id}
            href={`/marketplace/${sub.listing_id}`}
            className="block"
          >
            <GlassmorphismCard hover={false}>
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium font-mono text-muted-foreground">
                      Listing {sub.listing_id.slice(0, 8)}…
                    </span>
                    <Badge
                      className={cn(
                        "uppercase text-[10px]",
                        sub.status === "active"
                          ? "bg-profit/15 text-profit border-profit/30"
                          : "bg-white/[0.04] text-muted-foreground border-white/[0.06]",
                      )}
                    >
                      {sub.status}
                    </Badge>
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Subscribed {new Date(sub.subscribed_at).toLocaleDateString("en-IN")}
                    {sub.amount_paid_inr > 0
                      ? ` · ₹${sub.amount_paid_inr.toLocaleString("en-IN")} (stub)`
                      : " · FREE"}
                  </p>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </div>
            </GlassmorphismCard>
          </Link>
        ))}
      </div>
    </section>
  );
}

function MyListingsView({
  listings,
  isCreator,
  onRefresh,
}: {
  listings: CreatorListingData[];
  isCreator: boolean;
  onRefresh: () => void;
}) {
  if (!isCreator) {
    return (
      <GlassmorphismCard hover={false}>
        <p className="text-sm leading-relaxed">
          Sirf creator role wale users yahan listings manage kar
          sakte hain. Apgrade karne ke liye admin se contact karo.
        </p>
      </GlassmorphismCard>
    );
  }
  if (listings.length === 0) {
    return (
      <GlassmorphismCard hover={false}>
        <div className="space-y-2">
          <p className="text-sm leading-relaxed">
            Abhi koi listing nahi hai. Pehle ek strategy banao,
            phir use marketplace mein publish karo.
          </p>
          <p className="text-[11px] text-muted-foreground">
            (Phase 3 frontend abhi listing-create UI nahi ship karta —
            backend POST /api/marketplace/listings hit karke draft
            listing banao, ya admin tooling se Phase 4 wait karo.)
          </p>
        </div>
      </GlassmorphismCard>
    );
  }
  return (
    <div className="space-y-3">
      {listings.map((listing) => (
        <CreatorDashboardCard
          key={listing.id}
          listing={listing}
          onChange={onRefresh}
        />
      ))}
    </div>
  );
}
