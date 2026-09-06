/**
 * /indicators — ONE indicators page.
 *
 * Merged from the two that existed: /indicators (an educational glossary driven
 * by the local content registry) and /strategies/indicators (the API-backed
 * catalog). They listed different things and neither was authoritative.
 *
 * THE API CATALOG IS THE SOURCE. It decides WHICH indicators exist, and their
 * status and difficulty — a card appears here because the platform actually
 * supports that indicator, not because someone wrote a guide for it.
 * THE EDUCATIONAL CONTENT IS ITS DETAIL. Clicking a card opens the guide from
 * the content registry. An indicator the platform supports but has no guide for
 * still appears, and says so, rather than being hidden.
 *
 * /strategies/indicators redirects here.
 */

"use client";

import { motion } from "framer-motion";
import { AlertTriangle, BookOpen, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import { ProPage, ProEmpty } from "@/components/dashboard/pro-page";
import { IndicatorDetailModal } from "@/components/indicators/IndicatorDetailModal";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import type { IndicatorMetadata } from "@/components/strategies/indicator-library";
import { getIndicator } from "@/lib/indicators/registry";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.04 } } };
const fadeUp = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } };

const DIFFICULTY_STYLES: Record<string, string> = {
  beginner: "bg-emerald-500/10 text-emerald-400",
  intermediate: "bg-amber-500/10 text-amber-400",
  expert: "bg-rose-500/10 text-rose-400",
};

export default function IndicatorsPage() {
  const { data, isLoading, error, refetch } = useApi<IndicatorMetadata[]>(
    "/strategies/indicators",
    null,
  );
  const [query, setQuery] = useState("");
  const [openSlug, setOpenSlug] = useState<string | null>(null);

  const indicators = useMemo(() => data ?? [], [data]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return indicators;
    return indicators.filter(
      (i) =>
        i.name.toLowerCase().includes(q) ||
        i.category.toLowerCase().includes(q) ||
        (i.description ?? "").toLowerCase().includes(q),
    );
  }, [indicators, query]);

  return (
    <ProPage>
      {error && (
        <GlassmorphismCard className="flex items-center justify-between gap-4 p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            Indicator list load nahi hui.
          </div>
          <Button variant="ghost" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Phir se
          </Button>
        </GlassmorphismCard>
      )}

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Indicator dhoondo — naam ya kaam se"
        aria-label="Search indicators"
        className="w-full rounded-lg border bg-background px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-ring"
      />

      {isLoading && <p className="text-sm text-muted-foreground">Load ho raha hai…</p>}

      {!isLoading && !error && shown.length === 0 && (
        <ProEmpty
          headline={query ? "Is naam ka koi indicator nahi mila" : "Abhi koi indicator nahi hai"}
          next={
            query
              ? "Spelling check karo, ya poori list dekhne ke liye search khaali karo."
              : "Indicator list server se aati hai. Thodi der baad phir dekho, ya support ko batao."
          }
          action={query ? undefined : { label: "Support se poocho", href: "/help" }}
        />
      )}

      <motion.div
        variants={stagger}
        initial="hidden"
        animate="show"
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        {shown.map((ind) => {
          const guide = getIndicator(ind.id);
          return (
            <motion.button
              key={ind.id}
              variants={fadeUp}
              type="button"
              onClick={() => guide && setOpenSlug(ind.id)}
              data-indicator-id={ind.id}
              data-has-guide={guide ? "yes" : "no"}
              className={cn(
                "rounded-xl border p-4 text-left transition-colors",
                guide ? "hover:border-primary/50" : "cursor-default opacity-90",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium">{ind.name}</span>
                <span
                  className={cn(
                    "shrink-0 rounded px-1.5 py-0.5 text-[10px]",
                    DIFFICULTY_STYLES[ind.difficulty] ?? "bg-muted text-muted-foreground",
                  )}
                >
                  {ind.difficulty}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{ind.category}</p>
              <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                {ind.description}
              </p>
              <p className="mt-3 flex items-center gap-1 text-xs text-primary">
                <BookOpen className="h-3 w-3" />
                {guide ? "Poora guide padho" : "Guide abhi likhi ja rahi hai"}
              </p>
            </motion.button>
          );
        })}
      </motion.div>

      <IndicatorDetailModal
        open={openSlug !== null}
        slug={openSlug}
        onClose={() => setOpenSlug(null)}
      />
    </ProPage>
  );
}
