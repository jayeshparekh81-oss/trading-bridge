/**
 * CategorySidebar — sticky vertical list on desktop, accordion on
 * mobile. Clicking a category filters the FAQ accordion to that
 * category only (or "All" to clear the filter).
 *
 * Active state uses an emerald-400 accent matching the dashboard's
 * existing button + chart-marker accents.
 */

"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import type { CategoryMeta, FAQCategory } from "@/lib/help/faq-content";
import type { Lang } from "./LangToggle";

export interface CategorySidebarProps {
  categories: readonly CategoryMeta[];
  active: FAQCategory | null;
  onChange: (next: FAQCategory | null) => void;
  /** Bucket counts (per-category match counts so the operator can
   *  scan "where is everything"). Keys are category ids. */
  counts: Readonly<Record<FAQCategory, number>>;
  lang: Lang;
}

export function CategorySidebar({
  categories,
  active,
  onChange,
  counts,
  lang,
}: CategorySidebarProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const totalCount = Object.values(counts).reduce((a, b) => a + b, 0);
  const allLabel = lang === "hi" ? "Sabhi" : "All";

  return (
    <>
      {/* Mobile: collapsible header */}
      <div className="md:hidden mb-3">
        <button
          type="button"
          data-testid="help-category-mobile-toggle"
          onClick={() => setMobileOpen((v) => !v)}
          className="flex w-full items-center justify-between rounded-lg border border-white/10 bg-neutral-900/60 px-3 py-2 text-sm text-neutral-200"
        >
          <span>
            {active
              ? (lang === "hi"
                  ? categories.find((c) => c.id === active)?.label_hi
                  : categories.find((c) => c.id === active)?.label_en)
              : allLabel}
          </span>
          <ChevronDown
            className={`h-4 w-4 transition-transform ${mobileOpen ? "rotate-180" : ""}`}
            aria-hidden="true"
          />
        </button>
      </div>

      <nav
        data-testid="help-category-sidebar"
        aria-label="FAQ categories"
        className={`${mobileOpen ? "block" : "hidden"} md:block md:sticky md:top-4`}
      >
        <ul className="space-y-1">
          <li>
            <CategoryButton
              label={allLabel}
              isActive={active === null}
              count={totalCount}
              onClick={() => {
                onChange(null);
                setMobileOpen(false);
              }}
              testId="help-category-all"
            />
          </li>
          {categories.map((c) => (
            <li key={c.id}>
              <CategoryButton
                label={lang === "hi" ? c.label_hi : c.label_en}
                isActive={active === c.id}
                count={counts[c.id] ?? 0}
                onClick={() => {
                  onChange(c.id);
                  setMobileOpen(false);
                }}
                testId={`help-category-${c.id}`}
              />
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}

interface CategoryButtonProps {
  label: string;
  isActive: boolean;
  count: number;
  onClick: () => void;
  testId: string;
}

function CategoryButton({ label, isActive, count, onClick, testId }: CategoryButtonProps) {
  return (
    <button
      type="button"
      data-testid={testId}
      aria-pressed={isActive}
      onClick={onClick}
      className={`flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
        isActive
          ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30"
          : "text-neutral-300 hover:bg-white/5 border border-transparent"
      }`}
    >
      <span className="truncate">{label}</span>
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
          isActive
            ? "bg-emerald-500/20 text-emerald-300"
            : "bg-white/5 text-neutral-500"
        }`}
      >
        {count}
      </span>
    </button>
  );
}
