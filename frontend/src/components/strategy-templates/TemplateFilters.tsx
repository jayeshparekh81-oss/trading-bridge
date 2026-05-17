/**
 * TemplateFilters — left rail of the catalog page.
 *
 * Filters: search box, category select, complexity select, segment
 * select, "show inactive" toggle. All controls are uncontrolled
 * from this component's perspective — values + setters come from
 * the gallery's local state via props.
 */

"use client";

import { Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type {
  CategoryCounts,
  Complexity,
  Segment,
} from "@/lib/strategy-templates/types";

export interface TemplateFiltersProps {
  search: string;
  onSearchChange: (next: string) => void;

  category: string | null;
  onCategoryChange: (next: string | null) => void;

  complexity: Complexity | null;
  onComplexityChange: (next: Complexity | null) => void;

  segment: Segment | null;
  onSegmentChange: (next: Segment | null) => void;

  showInactive: boolean;
  onShowInactiveChange: (next: boolean) => void;

  categoryCounts: CategoryCounts | null;
  isLoadingCounts: boolean;
}

const COMPLEXITY_OPTIONS: Complexity[] = [
  "beginner",
  "intermediate",
  "advanced",
  "expert",
];

const SEGMENT_OPTIONS: { value: Segment; label: string }[] = [
  { value: "EQUITY", label: "Equity" },
  { value: "OPTIONS", label: "Options" },
];

export function TemplateFilters({
  search,
  onSearchChange,
  category,
  onCategoryChange,
  complexity,
  onComplexityChange,
  segment,
  onSegmentChange,
  showInactive,
  onShowInactiveChange,
  categoryCounts,
  isLoadingCounts,
}: TemplateFiltersProps) {
  const hasAnyFilter =
    !!search ||
    category !== null ||
    complexity !== null ||
    segment !== null ||
    showInactive !== true;

  function clearAll() {
    onSearchChange("");
    onCategoryChange(null);
    onComplexityChange(null);
    onSegmentChange(null);
    onShowInactiveChange(true);
  }

  return (
    <aside
      data-testid="template-filters"
      className="rounded-xl border border-border bg-card/40 p-4 space-y-5 md:sticky md:top-20 md:h-fit"
    >
      <div>
        <label className="block text-xs uppercase font-semibold tracking-wide text-muted-foreground mb-2">
          Search
        </label>
        <div className="relative">
          <Search
            className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="ema, supertrend, …"
            data-testid="template-filter-search"
            className="w-full h-8 pl-8 pr-3 rounded-md bg-muted/50 border border-border text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs uppercase font-semibold tracking-wide text-muted-foreground mb-2">
          Segment
        </label>
        <div className="flex gap-2">
          {SEGMENT_OPTIONS.map((opt) => {
            const selected = segment === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() =>
                  onSegmentChange(selected ? null : opt.value)
                }
                data-testid={`template-filter-segment-${opt.value}`}
                className={cn(
                  "flex-1 rounded-md border px-2 py-1 text-xs font-medium transition-colors",
                  selected
                    ? "border-accent-blue/50 bg-accent-blue/10 text-accent-blue"
                    : "border-border bg-muted/40 text-muted-foreground hover:text-foreground",
                )}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <label className="block text-xs uppercase font-semibold tracking-wide text-muted-foreground mb-2">
          Complexity
        </label>
        <div className="grid grid-cols-2 gap-2">
          {COMPLEXITY_OPTIONS.map((c) => {
            const selected = complexity === c;
            return (
              <button
                key={c}
                type="button"
                onClick={() => onComplexityChange(selected ? null : c)}
                data-testid={`template-filter-complexity-${c}`}
                className={cn(
                  "rounded-md border px-2 py-1 text-[11px] font-medium capitalize transition-colors",
                  selected
                    ? "border-accent-blue/50 bg-accent-blue/10 text-accent-blue"
                    : "border-border bg-muted/40 text-muted-foreground hover:text-foreground",
                )}
              >
                {c}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <label className="block text-xs uppercase font-semibold tracking-wide text-muted-foreground mb-2">
          Category
        </label>
        <div
          data-testid="template-filter-categories"
          className="max-h-60 overflow-y-auto pr-1 space-y-1"
        >
          {isLoadingCounts ? (
            <p className="text-xs text-muted-foreground">Loading…</p>
          ) : (
            (categoryCounts?.items ?? []).map((c) => {
              const selected = category === c.category;
              return (
                <button
                  key={c.category}
                  type="button"
                  onClick={() =>
                    onCategoryChange(selected ? null : c.category)
                  }
                  data-testid={`template-filter-category-${c.category}`}
                  className={cn(
                    "w-full flex items-center justify-between rounded-md px-2 py-1 text-xs transition-colors",
                    selected
                      ? "bg-accent-blue/10 text-accent-blue"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/30",
                  )}
                >
                  <span className="truncate text-left">{c.category}</span>
                  <span className="shrink-0 ml-2 tabular-nums">
                    {c.active}/{c.total}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </div>

      <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
        <input
          type="checkbox"
          checked={showInactive}
          onChange={(e) => onShowInactiveChange(e.target.checked)}
          data-testid="template-filter-show-inactive"
        />
        Show coming-soon templates
      </label>

      {hasAnyFilter && (
        <Button
          variant="ghost"
          size="sm"
          onClick={clearAll}
          data-testid="template-filter-clear"
          className="w-full text-xs"
        >
          <X className="h-3 w-3 mr-1" />
          Clear all filters
        </Button>
      )}
    </aside>
  );
}
