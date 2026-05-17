/**
 * /help — Customer FAQ page.
 *
 * Layout:
 *   - Header (title + lang toggle)
 *   - Search bar (full-width, debounced)
 *   - Two-column grid on desktop:
 *       * Left: sticky CategorySidebar (collapsible accordion on mobile)
 *       * Right: FAQAccordion (filtered by search + category)
 *   - Footer CTA → opens AlgoMitra chat
 *
 * Language follows the global `tradetri_lang` localStorage key, the
 * same one the onboarding tour uses — so switching language anywhere
 * carries over here.
 *
 * Search index: simple substring match across question + answer +
 * tags in the active language. Stays under 1ms for 35 FAQs and
 * doesn't need an external search lib.
 */

"use client";

import { motion } from "framer-motion";
import { HelpCircle, MessageCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CategorySidebar } from "@/components/help/CategorySidebar";
import { FAQAccordion } from "@/components/help/FAQAccordion";
import { FAQSearch } from "@/components/help/FAQSearch";
import {
  LangToggle,
  readLang,
  writeLang,
  type Lang,
} from "@/components/help/LangToggle";
import { Button } from "@/components/ui/button";
import {
  CATEGORIES,
  FAQS,
  type FAQ,
  type FAQCategory,
} from "@/lib/help/faq-content";

const HEADER_COPY = {
  title: { en: "Help & Support — Customer FAQ", hi: "Help aur Support — FAQ" },
  subtitle: {
    en: "Find answers fast. Still stuck? Chat with AlgoMitra at the bottom-right.",
    hi: "Jaldi answer dhundo. Phir bhi kuch na mile? Bottom-right pe AlgoMitra se baat karo.",
  },
  searchPlaceholder: {
    en: "Search FAQs — try 'broker', 'kill switch', 'backtest'",
    hi: "FAQs search karo — 'broker', 'kill switch', 'backtest' try karo",
  },
  algomitraCta: {
    en: "More questions? Ask AlgoMitra 🤖",
    hi: "Aur questions hai? AlgoMitra se pucho 🤖",
  },
  algomitraButton: { en: "Open AlgoMitra", hi: "AlgoMitra kholo" },
} as const;

export default function HelpPage() {
  const [lang, setLang] = useState<Lang>("hi");
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState<FAQCategory | null>(null);

  // Mirror the global lang on mount (localStorage) so a user who
  // picked "en" on the welcome modal lands on the English copy here.
  useEffect(() => {
    setLang(readLang());
  }, []);

  const handleLangChange = useCallback((next: Lang) => {
    setLang(next);
    writeLang(next);
  }, []);

  const handleSearchChange = useCallback((next: string) => {
    setSearch(next);
  }, []);

  // Apply search filter once (operates over all FAQs); used for both
  // the category-bucket counts (so users see "0" if their query
  // eliminates a category) and the final visible list.
  const searchFiltered = useMemo<FAQ[]>(() => {
    const q = search.trim().toLowerCase();
    if (q === "") return [...FAQS];
    return FAQS.filter((f) => {
      const fields = [
        lang === "hi" ? f.question_hi : f.question_en,
        lang === "hi" ? f.answer_hi : f.answer_en,
        ...f.tags,
      ];
      return fields.some((s) => s.toLowerCase().includes(q));
    });
  }, [search, lang]);

  const counts = useMemo<Record<FAQCategory, number>>(() => {
    const out: Record<FAQCategory, number> = {
      "getting-started": 0,
      account: 0,
      brokers: 0,
      chart: 0,
      strategies: 0,
      backtest: 0,
      "live-trading": 0,
      pricing: 0,
      compliance: 0,
      troubleshooting: 0,
    };
    for (const f of searchFiltered) out[f.category] += 1;
    return out;
  }, [searchFiltered]);

  const visible = useMemo<FAQ[]>(() => {
    if (activeCategory === null) return searchFiltered;
    return searchFiltered.filter((f) => f.category === activeCategory);
  }, [searchFiltered, activeCategory]);

  const handleAlgoMitra = useCallback(() => {
    const btn = document.querySelector<HTMLButtonElement>(
      'button[aria-label="Open AlgoMitra chat"]',
    );
    btn?.click();
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      data-testid="help-page"
      className="mx-auto max-w-6xl space-y-5 p-4 md:p-6 lg:p-8"
    >
      {/* Header */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h1
            data-testid="help-title"
            className="flex items-center gap-2 text-2xl font-bold text-neutral-100"
          >
            <HelpCircle className="h-6 w-6 text-emerald-400" aria-hidden="true" />
            {HEADER_COPY.title[lang]}
          </h1>
          <p className="max-w-2xl text-xs leading-relaxed text-neutral-400">
            {HEADER_COPY.subtitle[lang]}
          </p>
        </div>
        <LangToggle lang={lang} onChange={handleLangChange} />
      </header>

      {/* Search */}
      <FAQSearch
        onChange={handleSearchChange}
        placeholder={HEADER_COPY.searchPlaceholder[lang]}
      />

      {/* Two-column body */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-[240px_1fr]">
        <aside>
          <CategorySidebar
            categories={CATEGORIES}
            active={activeCategory}
            onChange={setActiveCategory}
            counts={counts}
            lang={lang}
          />
        </aside>

        <main>
          <FAQAccordion
            faqs={visible}
            lang={lang}
            emptyMessage={
              lang === "hi"
                ? "Koi match nahi mila. Search query alag try karo ya AlgoMitra se pucho."
                : "No matching FAQs. Try a different search or ask AlgoMitra."
            }
          />
        </main>
      </div>

      {/* AlgoMitra footer CTA */}
      <footer
        data-testid="help-algomitra-cta"
        className="mt-4 rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 p-5 supports-backdrop-filter:backdrop-blur-md"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-semibold text-neutral-100">
              {HEADER_COPY.algomitraCta[lang]}
            </p>
            <p className="text-xs text-neutral-400">
              {lang === "hi"
                ? "24×7 available — strategy ideas, indicator help, trading psychology, sab."
                : "Available 24×7 — strategy ideas, indicator help, trading psychology."}
            </p>
          </div>
          <Button
            type="button"
            onClick={handleAlgoMitra}
            data-testid="help-algomitra-button"
            className="bg-emerald-500 text-emerald-950 hover:bg-emerald-400"
          >
            <MessageCircle className="mr-1.5 h-4 w-4" aria-hidden="true" />
            {HEADER_COPY.algomitraButton[lang]}
          </Button>
        </div>
      </footer>
    </motion.div>
  );
}
