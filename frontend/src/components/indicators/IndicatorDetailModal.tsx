/**
 * IndicatorDetailModal — full-screen-on-mobile / centered-on-desktop
 * modal showing the complete educational content for a single
 * indicator. Bilingual via internal LangToggle (state lifted into
 * the modal so a user can switch languages without losing context).
 *
 * Controlled component: parent owns the `open` + `slug` state.
 */

"use client";

import { motion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { IndicatorBadge } from "./IndicatorBadge";
import { ConventionWarning } from "./ConventionWarning";
import { Button } from "@/components/ui/button";
import {
  LangToggle,
  readLang,
  writeLang,
  type Lang,
} from "@/components/help/LangToggle";
import { getIndicator } from "@/lib/indicators/registry";

export interface IndicatorDetailModalProps {
  open: boolean;
  slug: string | null;
  onClose: () => void;
}

export function IndicatorDetailModal({
  open,
  slug,
  onClose,
}: IndicatorDetailModalProps) {
  const [lang, setLang] = useState<Lang>("hi");

  useEffect(() => {
    if (open) setLang(readLang());
  }, [open]);

  if (!open || !slug) return null;
  const ind = getIndicator(slug);
  if (!ind) return null;

  const handleLang = (next: Lang) => {
    setLang(next);
    writeLang(next);
  };

  const oneLiner = lang === "hi" ? ind.one_liner_hi : ind.one_liner_en;
  const description = lang === "hi" ? ind.description_hi : ind.description_en;
  const periodLabel = lang === "hi" ? "Default period" : "Default period";
  const useCasesLabel = lang === "hi" ? "Kab use karein" : "Use cases";
  const signalsLabel = lang === "hi" ? "Signals" : "Signals";
  const pitfallsLabel = lang === "hi" ? "Saavdhaaniyaan" : "Pitfalls";
  const formulaLabel = lang === "hi" ? "Math (English only)" : "Formula";
  const indianLabel = lang === "hi" ? "Indian market context" : "Indian market context";
  const pairsWellLabel = lang === "hi" ? "Acche pairs" : "Works well with";
  const examplesLabel = lang === "hi" ? "Sample strategies" : "Example strategies";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="indicator-modal-title"
      data-testid="indicator-detail-modal"
      data-slug={slug}
      className="fixed inset-0 z-[70] flex items-end justify-center bg-black/70 supports-backdrop-filter:backdrop-blur-sm p-0 sm:items-center sm:p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl border border-white/10 bg-neutral-900/95 supports-backdrop-filter:backdrop-blur-xl p-5 shadow-2xl shadow-black/60 sm:rounded-2xl"
      >
        {/* Header */}
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="space-y-1">
            <h2
              id="indicator-modal-title"
              data-testid="indicator-modal-title"
              className="text-lg font-bold text-neutral-100"
            >
              {ind.name}
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <IndicatorBadge category={ind.category} />
              <span className="text-[10px] uppercase tracking-wide text-neutral-500">
                {ind.complexity}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <LangToggle lang={lang} onChange={handleLang} />
            <button
              type="button"
              aria-label="Close"
              onClick={onClose}
              data-testid="indicator-modal-close"
              className="rounded-md p-1 text-neutral-400 hover:bg-white/5 hover:text-neutral-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* One-liner */}
        <p
          data-testid="indicator-modal-oneliner"
          className="mb-4 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-sm leading-relaxed text-neutral-200"
        >
          {oneLiner}
        </p>

        {/* Convention-varies notice (renders only for the 6 Sprint 8d slugs) */}
        <ConventionWarning slug={slug} variant="full" className="mb-4" />

        {/* Description (paragraphs) */}
        <section className="mb-5 space-y-3 text-sm leading-relaxed text-neutral-300">
          {description.split("\n\n").map((para, i) => (
            <p key={i} data-testid={`indicator-modal-para-${i}`}>
              {para}
            </p>
          ))}
        </section>

        {/* Quick facts */}
        <section
          data-testid="indicator-modal-facts"
          className="mb-5 grid grid-cols-2 gap-2 text-xs"
        >
          {ind.default_period !== null && (
            <Fact label={periodLabel} value={String(ind.default_period)} />
          )}
          {ind.common_periods.length > 0 && (
            <Fact
              label="Common periods"
              value={ind.common_periods.join(", ")}
            />
          )}
          {ind.works_well_with.length > 0 && (
            <Fact
              label={pairsWellLabel}
              value={ind.works_well_with.join(", ")}
            />
          )}
          {ind.example_strategies.length > 0 && (
            <Fact
              label={examplesLabel}
              value={ind.example_strategies.join(" · ")}
            />
          )}
        </section>

        {/* Use cases */}
        <Section
          title={useCasesLabel}
          data-testid="indicator-modal-use-cases"
        >
          <ul className="space-y-2 text-sm text-neutral-300">
            {ind.use_cases.map((uc, i) => (
              <li
                key={i}
                className="rounded-lg border border-white/5 bg-white/[0.02] p-3"
              >
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-400">
                  {uc.scenario}
                </p>
                <p className="mb-1">{uc.what_to_do}</p>
                <p className="text-[11px] leading-relaxed text-neutral-400">
                  {uc.why}
                </p>
              </li>
            ))}
          </ul>
        </Section>

        {/* Common signals */}
        <Section
          title={signalsLabel}
          data-testid="indicator-modal-signals"
        >
          <ul className="space-y-1.5 text-sm text-neutral-300">
            {ind.common_signals.map((s, i) => (
              <li key={i} className="rounded-md border border-white/5 px-3 py-2">
                <p className="text-xs font-semibold text-neutral-100">
                  {s.signal}
                </p>
                <p className="text-[12px] text-neutral-400">
                  Condition: {s.condition}
                </p>
                <p className="text-[12px] text-neutral-400">
                  Action: {s.action}
                </p>
              </li>
            ))}
          </ul>
        </Section>

        {/* Pitfalls */}
        <Section title={pitfallsLabel} data-testid="indicator-modal-pitfalls">
          <ul className="list-disc space-y-1 pl-5 text-sm text-neutral-300">
            {ind.pitfalls.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </Section>

        {/* Formula (always English — math is universal) */}
        <Section title={formulaLabel} data-testid="indicator-modal-formula">
          <p className="text-sm leading-relaxed text-neutral-300">
            {ind.formula_explanation}
          </p>
        </Section>

        {/* Indian context */}
        <Section
          title={indianLabel}
          data-testid="indicator-modal-indian-context"
        >
          <p className="text-sm leading-relaxed text-neutral-300">
            {ind.indian_context}
          </p>
        </Section>

        {/* Close button at the bottom (mobile friendly) */}
        <div className="mt-6 flex justify-end">
          <Button
            type="button"
            onClick={onClose}
            data-testid="indicator-modal-close-bottom"
            className="bg-emerald-500 text-emerald-950 hover:bg-emerald-400"
          >
            {lang === "hi" ? "Band karo" : "Close"}
          </Button>
        </div>
      </motion.div>
    </div>
  );
}

function Section({
  title,
  children,
  ...rest
}: {
  title: string;
  children: React.ReactNode;
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <section className="mb-5" {...rest}>
      <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/5 bg-white/[0.02] p-2">
      <p className="text-[9px] uppercase tracking-wide text-neutral-500">
        {label}
      </p>
      <p className="text-xs font-medium text-neutral-200">{value}</p>
    </div>
  );
}
