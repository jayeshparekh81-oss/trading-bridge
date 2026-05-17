/**
 * /compliance/legal — long-form site-wide legal disclaimer.
 *
 * Distinct from /compliance, which is the per-strategy license
 * compliance dashboard (Apache / MIT / GPL of indicators). This
 * route owns the customer-facing legal text: risk, terms, SEBI
 * framework, data privacy, Glass Box AI, transparency ledger.
 *
 * Reuses the LangToggle from /help so the bilingual choice is
 * consistent with the rest of the dashboard.
 */

"use client";

import { motion } from "framer-motion";
import { ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  LangToggle,
  readLang,
  writeLang,
  type Lang,
} from "@/components/help/LangToggle";
import { DISCLAIMER_SECTIONS } from "@/lib/compliance/disclaimer-text";

const HEADER_COPY = {
  title: {
    en: "Risk Disclosure & Compliance",
    hi: "Risk Disclosure aur Compliance",
  },
  subtitle: {
    en: "The legal binding text — read before placing any live order.",
    hi: "Legal binding text — koi bhi live order place karne se pehle padho.",
  },
  toc: { en: "Sections", hi: "Sections" },
} as const;

export default function ComplianceLegalPage() {
  const [lang, setLang] = useState<Lang>("hi");

  useEffect(() => {
    setLang(readLang());
  }, []);

  const handleLangChange = useCallback((next: Lang) => {
    setLang(next);
    writeLang(next);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      data-testid="compliance-legal-page"
      className="mx-auto max-w-4xl space-y-6 p-4 md:p-6 lg:p-8"
    >
      {/* Header */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h1
            data-testid="compliance-legal-title"
            className="flex items-center gap-2 text-2xl font-bold text-neutral-100"
          >
            <ShieldAlert
              className="h-6 w-6 text-amber-400"
              aria-hidden="true"
            />
            {HEADER_COPY.title[lang]}
          </h1>
          <p className="max-w-2xl text-xs leading-relaxed text-neutral-400">
            {HEADER_COPY.subtitle[lang]}
          </p>
        </div>
        <LangToggle lang={lang} onChange={handleLangChange} />
      </header>

      {/* Table of contents */}
      <nav
        aria-label={HEADER_COPY.toc[lang]}
        data-testid="compliance-legal-toc"
        className="rounded-xl border border-white/10 bg-neutral-900/50 supports-backdrop-filter:backdrop-blur-md p-4"
      >
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
          {HEADER_COPY.toc[lang]}
        </p>
        <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
          {DISCLAIMER_SECTIONS.map((s) => (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                data-testid={`compliance-legal-toc-${s.id}`}
                className="block rounded-md px-2 py-1 text-sm text-neutral-300 hover:bg-white/5 hover:text-emerald-300"
              >
                {lang === "hi" ? s.title_hi : s.title_en}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {/* Sections */}
      <div className="space-y-5">
        {DISCLAIMER_SECTIONS.map((section) => (
          <section
            key={section.id}
            id={section.id}
            data-testid={`compliance-legal-section-${section.id}`}
            className="rounded-2xl border border-white/10 bg-neutral-900/50 supports-backdrop-filter:backdrop-blur-md p-5 scroll-mt-24"
          >
            <h2 className="mb-3 text-lg font-semibold text-neutral-100">
              {lang === "hi" ? section.title_hi : section.title_en}
            </h2>
            <div className="space-y-3 text-sm leading-relaxed text-neutral-300">
              {(lang === "hi" ? section.body_hi : section.body_en)
                .split("\n\n")
                .map((para, i) => (
                  <p key={i}>{renderInlineMd(para)}</p>
                ))}
            </div>
          </section>
        ))}
      </div>
    </motion.div>
  );
}

// ─── Inline markdown (same minimal tokeniser as /help FAQItem) ──────

function renderInlineMd(text: string): React.ReactNode {
  const re = /`([^`]+)`|\*\*([^*]+)\*\*/g;
  const out: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      out.push(<span key={key++}>{text.slice(last, m.index)}</span>);
    }
    if (m[1] !== undefined) {
      out.push(
        <code
          key={key++}
          className="rounded bg-white/5 px-1 py-0.5 font-mono text-[12px] text-emerald-300"
        >
          {m[1]}
        </code>,
      );
    } else if (m[2] !== undefined) {
      out.push(
        <strong key={key++} className="font-semibold text-neutral-100">
          {m[2]}
        </strong>,
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    out.push(<span key={key++}>{text.slice(last)}</span>);
  }
  return out;
}
