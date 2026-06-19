/**
 * /strategies/templates — the Strategy Template System catalog page.
 *
 * Header → live counts by status (Preview / Coming Soon / Options),
 *          computed from the loaded template list; empty buckets hidden.
 * Layout: left filter rail + responsive grid of TemplateCard tiles.
 * Detail modal opens on "View Details"; clone goes through
 * ``cloneTemplate`` → 201 → ``router.push("/strategies/${id}")``.
 */

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Sparkles, AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { TemplateCard } from "@/components/strategy-templates/TemplateCard";
import { TemplateDetailModal } from "@/components/strategy-templates/TemplateDetailModal";
import { TemplateFilters } from "@/components/strategy-templates/TemplateFilters";
import {
  cloneTemplate,
  fetchCategoryCounts,
  fetchTemplateDetail,
  fetchTemplates,
  type ApiError,
} from "@/lib/strategy-templates/api";
import type {
  CategoryCounts,
  Complexity,
  Segment,
  TemplateDetail,
  TemplateListResponse,
  TemplateSummary,
} from "@/lib/strategy-templates/types";

export default function StrategyTemplatesPage() {
  const router = useRouter();

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [complexity, setComplexity] = useState<Complexity | null>(null);
  const [segment, setSegment] = useState<Segment | null>(null);
  const [showInactive, setShowInactive] = useState(true);

  const [listResp, setListResp] = useState<TemplateListResponse | null>(
    null,
  );
  const [counts, setCounts] = useState<CategoryCounts | null>(null);
  const [isLoadingList, setLoadingList] = useState(true);
  const [isLoadingCounts, setLoadingCounts] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [detailSlug, setDetailSlug] = useState<string | null>(null);
  const [detail, setDetail] = useState<TemplateDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [cloningSlug, setCloningSlug] = useState<string | null>(null);
  const [cloneError, setCloneError] = useState<string | null>(null);

  // ── Initial load: list + category counts (parallel) ────────────
  const loadList = useCallback(async () => {
    setLoadingList(true);
    setListError(null);
    try {
      const resp = await fetchTemplates({
        category: category ?? undefined,
        complexity: complexity ?? undefined,
        segment: segment ?? undefined,
        search: search.trim() || undefined,
        is_active: showInactive ? undefined : true,
      });
      setListResp(resp);
    } catch (e) {
      const err = e as ApiError;
      setListError(err?.message ?? "Failed to load templates.");
    } finally {
      setLoadingList(false);
    }
  }, [category, complexity, segment, search, showInactive]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    let alive = true;
    setLoadingCounts(true);
    fetchCategoryCounts()
      .then((c) => {
        if (alive) setCounts(c);
      })
      .catch(() => {
        // Counts are non-critical; if the endpoint fails the filter
        // sidebar just shows no badges, but the list still renders.
      })
      .finally(() => {
        if (alive) setLoadingCounts(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  // ── Detail modal lifecycle ─────────────────────────────────────
  useEffect(() => {
    if (detailSlug === null) {
      setDetail(null);
      setDetailError(null);
      return;
    }
    let alive = true;
    setLoadingDetail(true);
    setDetailError(null);
    fetchTemplateDetail(detailSlug)
      .then((d) => {
        if (alive) setDetail(d);
      })
      .catch((e) => {
        const err = e as ApiError;
        if (alive)
          setDetailError(err?.message ?? "Failed to load template.");
      })
      .finally(() => {
        if (alive) setLoadingDetail(false);
      });
    return () => {
      alive = false;
    };
  }, [detailSlug]);

  // ── Handlers ───────────────────────────────────────────────────
  const handleView = useCallback((t: TemplateSummary) => {
    setDetailSlug(t.slug);
  }, []);

  const handleClone = useCallback(
    async (slug: string) => {
      setCloningSlug(slug);
      setCloneError(null);
      try {
        const resp = await cloneTemplate(slug);
        setDetailSlug(null);
        router.push(`/strategies/${resp.strategy_id}`);
      } catch (e) {
        const err = e as ApiError;
        setCloneError(err?.message ?? "Failed to clone template.");
      } finally {
        setCloningSlug(null);
      }
    },
    [router],
  );

  const handleCloneFromCard = useCallback(
    (t: TemplateSummary) => {
      void handleClone(t.slug);
    },
    [handleClone],
  );

  // ── Header counts (live, by status) ────────────────────────────
  // Computed from the loaded template list (``listResp.items``): the
  // full catalog in the default view, narrowing as filters apply.
  // Buckets — active = Preview, inactive & non-options = Coming Soon,
  // options-builder-required = Options. Empty buckets are hidden in the
  // header below, so we never render an invented category or a 0 count.
  const bucketCounts = useMemo(() => {
    const items = listResp?.items ?? [];
    const total = items.length;
    const active = items.filter((t) => t.is_active).length;
    const comingSoon = items.filter(
      (t) => !t.is_active && !t.requires_options_builder,
    ).length;
    const optionsPending = items.filter(
      (t) => t.requires_options_builder,
    ).length;
    return { total, active, comingSoon, optionsPending };
  }, [listResp]);

  return (
    <div className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto">
      {/* ── Header ─────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mb-6"
      >
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold inline-flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-accent-blue" aria-hidden="true" />
              Strategy Templates
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Browse {bucketCounts.active + bucketCounts.comingSoon + bucketCounts.optionsPending} strategies.
              Active configs preview-only until the Strategy Builder ships —
              clone to bookmark and review the template's setup.
            </p>
            <div
              data-testid="template-header-counts"
              className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs"
            >
              {bucketCounts.active > 0 && (
                <span className="inline-flex items-center gap-1 text-accent-blue">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent-blue" />
                  {bucketCounts.active} Preview
                </span>
              )}
              {bucketCounts.comingSoon > 0 && (
                <span className="inline-flex items-center gap-1 text-amber-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                  {bucketCounts.comingSoon} Coming Soon
                </span>
              )}
              {bucketCounts.optionsPending > 0 && (
                <span className="inline-flex items-center gap-1 text-accent-purple">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent-purple" />
                  {bucketCounts.optionsPending} Options (Phase 7-8)
                </span>
              )}
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void loadList()}
            data-testid="template-list-refresh"
          >
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </div>
      </motion.div>

      {cloneError && (
        <div
          data-testid="template-clone-error"
          className="mb-4 rounded-lg border border-loss/40 bg-loss/10 px-4 py-2 text-sm text-loss flex items-center gap-2"
        >
          <AlertTriangle className="h-4 w-4" />
          {cloneError}
        </div>
      )}

      {/* ── Body grid ──────────────────────────────────────────── */}
      <div className="grid gap-6 md:grid-cols-[260px,1fr]">
        <TemplateFilters
          search={search}
          onSearchChange={setSearch}
          category={category}
          onCategoryChange={setCategory}
          complexity={complexity}
          onComplexityChange={setComplexity}
          segment={segment}
          onSegmentChange={setSegment}
          showInactive={showInactive}
          onShowInactiveChange={setShowInactive}
          categoryCounts={counts}
          isLoadingCounts={isLoadingCounts}
        />

        <div data-testid="template-gallery">
          {isLoadingList && (
            <p
              data-testid="template-list-loading"
              className="py-10 text-center text-muted-foreground text-sm"
            >
              Loading templates…
            </p>
          )}

          {listError && !isLoadingList && (
            <GlassmorphismCard
              hover={false}
              className="text-center text-sm"
              glow="loss"
              data-testid="template-list-error"
            >
              <AlertTriangle className="h-6 w-6 text-loss mx-auto mb-2" />
              <p className="text-loss font-semibold">Could not load templates</p>
              <p className="text-muted-foreground mt-1">{listError}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => void loadList()}
              >
                Retry
              </Button>
            </GlassmorphismCard>
          )}

          {!isLoadingList &&
            !listError &&
            (listResp?.items.length ?? 0) === 0 && (
              <p
                data-testid="template-list-empty"
                className="py-10 text-center text-muted-foreground text-sm"
              >
                No templates match these filters.
              </p>
            )}

          {!isLoadingList && !listError && (listResp?.items.length ?? 0) > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {listResp?.items.map((t) => (
                <TemplateCard
                  key={t.id}
                  template={t}
                  onView={handleView}
                  onClone={handleCloneFromCard}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <TemplateDetailModal
        template={detail}
        isLoading={loadingDetail}
        error={detailError}
        onClose={() => setDetailSlug(null)}
        onClone={(slug) => void handleClone(slug)}
        cloning={cloningSlug === detail?.slug}
      />
    </div>
  );
}
