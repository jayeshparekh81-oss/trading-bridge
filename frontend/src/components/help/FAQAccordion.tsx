/**
 * FAQAccordion — list of FAQItems. Owns the open/closed Set so the
 * page-level component can stay focused on filtering + lang.
 *
 * Multiple items can be open at once (mirrors how users read docs —
 * compare two answers side-by-side without losing context).
 */

"use client";

import { useState } from "react";

import type { FAQ } from "@/lib/help/faq-content";
import { FAQItem } from "./FAQItem";
import type { Lang } from "./LangToggle";

export interface FAQAccordionProps {
  faqs: readonly FAQ[];
  lang: Lang;
  emptyMessage?: string;
}

export function FAQAccordion({
  faqs,
  lang,
  emptyMessage,
}: FAQAccordionProps) {
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());

  if (faqs.length === 0) {
    return (
      <div
        data-testid="help-faq-empty"
        className="rounded-xl border border-white/10 bg-neutral-900/50 px-4 py-8 text-center text-sm text-neutral-400"
      >
        {emptyMessage ?? (lang === "hi" ? "Koi result nahi mila." : "No results.")}
      </div>
    );
  }

  return (
    <div data-testid="help-faq-accordion" className="space-y-2">
      {faqs.map((faq) => {
        const isOpen = openIds.has(faq.id);
        return (
          <FAQItem
            key={faq.id}
            faq={faq}
            lang={lang}
            isOpen={isOpen}
            onToggle={() => {
              setOpenIds((prev) => {
                const next = new Set(prev);
                if (next.has(faq.id)) next.delete(faq.id);
                else next.add(faq.id);
                return next;
              });
            }}
          />
        );
      })}
    </div>
  );
}
