/**
 * /indicators — indicator glossary.
 *
 * Grid of cards for every indicator in the registry. Each card shows
 * name + category badge + one-liner. Click → open IndicatorDetailModal
 * with full content.
 *
 * Filters: search (free text), category dropdown, complexity dropdown.
 * Bilingual: shares `tradetri_lang` localStorage with /help and the
 * tour. Defaults to 'hi'.
 *
 * Existing `/indicators/requests` (admin user-requests inbox) lives
 * at a sibling route and is unaffected by this page.
 */

"use client";

import { motion } from "framer-motion";
import { BookOpen } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { IndicatorBadge } from "@/components/indicators/IndicatorBadge";
import { IndicatorDetailModal } from "@/components/indicators/IndicatorDetailModal";
import {
  LangToggle,
  readLang,
  writeLang,
  type Lang,
} from "@/components/help/LangToggle";
import { FAQSearch } from "@/components/help/FAQSearch";
import {
  filterIndicators,
  type IndicatorCategory,
  type IndicatorComplexity,
  type IndicatorContent,
} from "@/lib/indicators/registry";

const CATEGORY_OPTIONS: { value: IndicatorCategory | ""; label: string }[] = [
  { value: "", label: "All categories" },
  { value: "momentum", label: "Momentum" },
  { value: "trend", label: "Trend" },
  { value: "volatility", label: "Volatility" },
  { value: "volume", label: "Volume" },
  { value: "rate", label: "Rate" },
  { value: "pattern", label: "Pattern" },
  { value: "advanced", label: "Advanced" },
];

const COMPLEXITY_OPTIONS: { value: IndicatorComplexity | ""; label: string }[] = [
  { value: "", label: "All levels" },
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
];

const HEADER_COPY = {
  title: {
    en: "Indicator Library",
    hi: "Indicator Library",
  },
  subtitle: {
    en: "Comprehensive 70+ indicators library for Indian retail trading. Click any card for full details + India-specific notes.",
    hi: "Indian retail trading mein use hone wale 70+ indicators ki comprehensive library. Card click karke full details + India-specific notes dekho.",
  },
  searchPlaceholder: {
    en: "Search indicators — name, slug, or one-liner",
    hi: "Indicators search karo — name, slug, ya one-liner",
  },
  emptyState: {
    en: "No matching indicators. Try a different filter or search.",
    hi: "Koi matching indicator nahi. Different filter ya search try karo.",
  },
} as const;

export default function IndicatorsGlossaryPage() {
  const [lang, setLang] = useState<Lang>("hi");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<IndicatorCategory | "">("");
  const [complexity, setComplexity] = useState<IndicatorComplexity | "">("");
  const [openSlug, setOpenSlug] = useState<string | null>(null);

  useEffect(() => {
    setLang(readLang());
  }, []);

  const handleLang = useCallback((next: Lang) => {
    setLang(next);
    writeLang(next);
  }, []);

  const handleSearch = useCallback((q: string) => setSearch(q), []);

  const visible = useMemo<IndicatorContent[]>(() => {
    return filterIndicators({
      category: category === "" ? undefined : category,
      complexity: complexity === "" ? undefined : complexity,
      query: search,
    });
  }, [search, category, complexity]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      data-testid="indicators-glossary-page"
      className="mx-auto max-w-6xl space-y-5 p-4 md:p-6 lg:p-8"
    >
      {/* Header */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h1
            data-testid="indicators-glossary-title"
            className="flex items-center gap-2 text-2xl font-bold text-neutral-100"
          >
            <BookOpen
              className="h-6 w-6 text-emerald-400"
              aria-hidden="true"
            />
            {HEADER_COPY.title[lang]}
          </h1>
          <p className="max-w-2xl text-xs leading-relaxed text-neutral-400">
            {HEADER_COPY.subtitle[lang]}
          </p>
        </div>
        <LangToggle lang={lang} onChange={handleLang} />
      </header>

      {/* Filters */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
        <div className="flex-1">
          <FAQSearch
            onChange={handleSearch}
            placeholder={HEADER_COPY.searchPlaceholder[lang]}
          />
        </div>
        <select
          value={category}
          onChange={(e) =>
            setCategory(e.target.value as IndicatorCategory | "")
          }
          data-testid="indicators-category-filter"
          className="h-10 rounded-lg border border-white/10 bg-neutral-900/60 px-3 text-sm text-neutral-200 outline-none focus:border-emerald-500/50"
        >
          {CATEGORY_OPTIONS.map((opt) => (
            <option key={opt.value || "all-cat"} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select
          value={complexity}
          onChange={(e) =>
            setComplexity(e.target.value as IndicatorComplexity | "")
          }
          data-testid="indicators-complexity-filter"
          className="h-10 rounded-lg border border-white/10 bg-neutral-900/60 px-3 text-sm text-neutral-200 outline-none focus:border-emerald-500/50"
        >
          {COMPLEXITY_OPTIONS.map((opt) => (
            <option key={opt.value || "all-cx"} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Result count */}
      <p
        data-testid="indicators-result-count"
        className="text-xs text-neutral-500"
      >
        {visible.length}{" "}
        {lang === "hi" ? "indicators" : visible.length === 1 ? "indicator" : "indicators"}
      </p>

      {/* Grid */}
      {visible.length === 0 ? (
        <div
          data-testid="indicators-glossary-empty"
          className="rounded-xl border border-white/10 bg-neutral-900/50 px-4 py-12 text-center text-sm text-neutral-400"
        >
          {HEADER_COPY.emptyState[lang]}
        </div>
      ) : (
        <div
          data-testid="indicators-glossary-grid"
          className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
        >
          {visible.map((ind) => (
            <button
              key={ind.slug}
              type="button"
              data-testid={`indicators-card-${ind.slug}`}
              onClick={() => setOpenSlug(ind.slug)}
              className="group flex flex-col gap-2 rounded-xl border border-white/10 bg-neutral-900/50 supports-backdrop-filter:backdrop-blur-md p-4 text-left transition-colors hover:border-emerald-500/40 hover:bg-neutral-900/70"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-semibold text-neutral-100 group-hover:text-emerald-300">
                  {ind.name}
                </span>
                <IndicatorBadge category={ind.category} />
              </div>
              <span className="text-[10px] uppercase tracking-wide text-neutral-500">
                {ind.complexity}
              </span>
              <p className="text-xs leading-relaxed text-neutral-400">
                {lang === "hi" ? ind.one_liner_hi : ind.one_liner_en}
              </p>
            </button>
          ))}
        </div>
      )}

      {/* Detail modal */}
      <IndicatorDetailModal
        open={openSlug !== null}
        slug={openSlug}
        onClose={() => setOpenSlug(null)}
      />
    </motion.div>
  );
}
