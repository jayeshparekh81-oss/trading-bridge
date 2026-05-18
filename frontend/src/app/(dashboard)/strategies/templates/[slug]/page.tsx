/**
 * /strategies/templates/[slug] — customer-visible explainer for a
 * single strategy template.
 *
 * Reads from `@/lib/strategies/explainers` (44 explainers; the
 * registry is populated as Gate 2 lands the explainer-content
 * branch). When a slug has no explainer yet, renders a friendly
 * "explainer is being written" fallback rather than a 404.
 *
 * Bilingual via the same `tradetri_lang` localStorage key that the
 * /indicators and /help pages use — switching language anywhere
 * carries here.
 *
 * No backend calls; pure content render. The execution-side
 * Template browse and clone flow lives at /strategies/templates
 * and is untouched by this route.
 */

"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  AlertTriangle,
  BookOpen,
  ChevronRight,
  Lightbulb,
  Target,
  TrendingDown,
  TrendingUp,
  CircleDashed,
} from "lucide-react";

import {
  LangToggle,
  readLang,
  writeLang,
  type Lang,
} from "@/components/help/LangToggle";
import {
  getExplainer,
  type StrategyExplainer,
} from "@/lib/strategies/explainers";

interface PageProps {
  params: Promise<{ slug: string }>;
}

/* ────────────────────────────────────────────────────────────────
 * Tiny presentational helpers — kept inline because they're only
 * used here.
 * ────────────────────────────────────────────────────────────────*/

function ScoreDots({
  value,
  max = 5,
  label,
  testId,
}: {
  value: number;
  max?: number;
  label: string;
  testId: string;
}) {
  return (
    <div
      data-testid={testId}
      className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2"
    >
      <span className="text-[10px] uppercase tracking-wide text-neutral-500">
        {label}
      </span>
      <span className="flex items-center gap-0.5">
        {Array.from({ length: max }).map((_, i) => (
          <span
            key={i}
            aria-hidden="true"
            className={
              i < value
                ? "h-2 w-2 rounded-full bg-emerald-400"
                : "h-2 w-2 rounded-full bg-white/15"
            }
          />
        ))}
      </span>
      <span className="text-xs font-semibold text-neutral-200">
        {value}/{max}
      </span>
    </div>
  );
}

function MissingExplainerFallback({
  slug,
  lang,
}: {
  slug: string;
  lang: Lang;
}) {
  const copy =
    lang === "hi"
      ? {
          title: "Is template ka explainer abhi aur nahi likha gaya",
          body: "Hum 44 strategy templates ke detailed explainers ship kar chuke hain — yeh template uss set mein nahi tha. Sab available explainers dekhne ke liye Templates page pe wapas jao.",
          back: "Templates page wapas",
        }
      : {
          title: "Explainer not written for this template yet",
          body: "We ship detailed explainers for 44 strategy templates today; this one wasn't in that set. Head back to the Templates page to browse all available explainers.",
          back: "Back to Templates",
        };
  return (
    <div
      data-testid="explainer-missing"
      data-slug={slug}
      className="rounded-xl border border-white/10 bg-neutral-900/50 px-5 py-8 text-center"
    >
      <CircleDashed
        className="mx-auto mb-3 h-6 w-6 text-neutral-500"
        aria-hidden="true"
      />
      <h2 className="mb-2 text-base font-semibold text-neutral-100">
        {copy.title}
      </h2>
      <p className="mx-auto mb-5 max-w-md text-sm leading-relaxed text-neutral-400">
        {copy.body}
      </p>
      <Link
        href="/strategies/templates"
        data-testid="explainer-missing-back"
        className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-neutral-200 hover:border-emerald-500/40 hover:bg-white/[0.07]"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        {copy.back}
      </Link>
    </div>
  );
}

function ExplainerBody({
  explainer,
  lang,
}: {
  explainer: StrategyExplainer;
  lang: Lang;
}) {
  const labels =
    lang === "hi"
      ? {
          whatItDoes: "Kya karta hai",
          bestConditions: "Kab kaam karta hai",
          worstConditions: "Kab fail hota hai",
          commonMistakes: "Common galtiyaan",
          realisticReturns: "Realistic returns",
          exampleTrade: "Example trade",
          followUps: "Aage padho",
          difficulty: "Mushkil",
          capEff: "Capital efficiency",
          symbolLbl: "Symbol",
          entryLbl: "Entry",
          exitLbl: "Exit",
          pnlLbl: "P&L",
          disclaimer:
            "Yeh past performance examples hain. Live trading mein returns guarantee NAHI hote. Hamesha apna own paper backtest karo, fir hi position size kaam shuru karo.",
        }
      : {
          whatItDoes: "What it does",
          bestConditions: "Best market conditions",
          worstConditions: "Worst market conditions",
          commonMistakes: "Common mistakes",
          realisticReturns: "Realistic returns",
          exampleTrade: "Example trade",
          followUps: "Follow-up strategies",
          difficulty: "Difficulty",
          capEff: "Capital efficiency",
          symbolLbl: "Symbol",
          entryLbl: "Entry",
          exitLbl: "Exit",
          pnlLbl: "P&L",
          disclaimer:
            "These are past-performance examples. Live-trading returns are NOT guaranteed. Always paper-backtest on your own data before sizing any position.",
        };

  const whatItDoes = lang === "hi" ? explainer.what_it_does_hi : explainer.what_it_does;
  const paragraphs = whatItDoes.split("\n\n").filter((p) => p.trim().length > 0);

  return (
    <article
      data-testid="explainer-body"
      data-slug={explainer.slug}
      className="space-y-6"
    >
      {/* Scores row */}
      <div className="flex flex-wrap gap-2">
        <ScoreDots
          label={labels.difficulty}
          value={explainer.difficulty_score}
          testId="explainer-difficulty"
        />
        <ScoreDots
          label={labels.capEff}
          value={explainer.capital_efficiency_score}
          testId="explainer-capital-eff"
        />
      </div>

      {/* What it does */}
      <section
        data-testid="explainer-what-it-does"
        className="space-y-3 rounded-xl border border-white/10 bg-neutral-900/40 p-5"
      >
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-emerald-300">
          <BookOpen className="h-4 w-4" aria-hidden="true" />
          {labels.whatItDoes}
        </h2>
        <div className="space-y-3 text-sm leading-relaxed text-neutral-200">
          {paragraphs.map((para, i) => (
            <p key={i} data-testid={`explainer-what-para-${i}`}>
              {para}
            </p>
          ))}
        </div>
      </section>

      {/* Best vs Worst conditions */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <section
          data-testid="explainer-best-conditions"
          className="space-y-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4"
        >
          <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-emerald-300">
            <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
            {labels.bestConditions}
          </h3>
          <p className="text-sm leading-relaxed text-neutral-200">
            {explainer.best_market_conditions}
          </p>
        </section>
        <section
          data-testid="explainer-worst-conditions"
          className="space-y-2 rounded-xl border border-red-500/20 bg-red-500/5 p-4"
        >
          <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-red-300">
            <TrendingDown className="h-3.5 w-3.5" aria-hidden="true" />
            {labels.worstConditions}
          </h3>
          <p className="text-sm leading-relaxed text-neutral-200">
            {explainer.worst_market_conditions}
          </p>
        </section>
      </div>

      {/* Common mistakes */}
      <section
        data-testid="explainer-mistakes"
        className="space-y-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-5"
      >
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-amber-300">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          {labels.commonMistakes}
        </h2>
        <ol className="ml-4 list-decimal space-y-2 text-sm leading-relaxed text-neutral-200">
          {explainer.common_mistakes.map((m, i) => (
            <li key={i} data-testid={`explainer-mistake-${i}`}>
              {m}
            </li>
          ))}
        </ol>
      </section>

      {/* Realistic returns — callout with disclaimer */}
      <section
        data-testid="explainer-returns"
        className="space-y-2 rounded-xl border border-white/10 bg-neutral-900/40 p-5"
      >
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-neutral-200">
          <Target className="h-4 w-4 text-sky-400" aria-hidden="true" />
          {labels.realisticReturns}
        </h2>
        <p
          data-testid="explainer-returns-body"
          className="text-sm leading-relaxed text-neutral-300"
        >
          {explainer.realistic_returns}
        </p>
        <p
          data-testid="explainer-disclaimer"
          className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-[11px] leading-relaxed text-amber-200"
        >
          ⚠ {labels.disclaimer}
        </p>
      </section>

      {/* Example trade */}
      <section
        data-testid="explainer-example"
        className="space-y-3 rounded-xl border border-white/10 bg-neutral-900/40 p-5"
      >
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-neutral-200">
          <Lightbulb className="h-4 w-4 text-yellow-400" aria-hidden="true" />
          {labels.exampleTrade}
        </h2>
        <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-[11px] uppercase tracking-wide text-neutral-500">
            {labels.symbolLbl}
          </dt>
          <dd
            data-testid="explainer-example-symbol"
            className="font-mono text-neutral-100"
          >
            {explainer.example_trade.symbol}
          </dd>
          <dt className="text-[11px] uppercase tracking-wide text-neutral-500">
            {labels.entryLbl}
          </dt>
          <dd
            data-testid="explainer-example-entry"
            className="text-neutral-200"
          >
            {explainer.example_trade.entry}
          </dd>
          <dt className="text-[11px] uppercase tracking-wide text-neutral-500">
            {labels.exitLbl}
          </dt>
          <dd data-testid="explainer-example-exit" className="text-neutral-200">
            {explainer.example_trade.exit}
          </dd>
          <dt className="text-[11px] uppercase tracking-wide text-neutral-500">
            {labels.pnlLbl}
          </dt>
          <dd
            data-testid="explainer-example-pnl"
            className="font-mono text-emerald-300"
          >
            {explainer.example_trade.pnl}
          </dd>
        </dl>
      </section>

      {/* Follow-ups */}
      {explainer.follow_up_strategies.length > 0 && (
        <section
          data-testid="explainer-followups"
          className="space-y-3 rounded-xl border border-white/10 bg-neutral-900/40 p-5"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-200">
            {labels.followUps}
          </h2>
          <ul className="space-y-1.5">
            {explainer.follow_up_strategies.map((s) => {
              const target = getExplainer(s);
              return (
                <li key={s}>
                  <Link
                    href={`/strategies/templates/${s}`}
                    data-testid={`explainer-followup-${s}`}
                    className="group inline-flex items-center gap-1.5 text-sm text-neutral-300 hover:text-emerald-300"
                  >
                    <ChevronRight
                      className="h-3.5 w-3.5 text-neutral-500 group-hover:text-emerald-400"
                      aria-hidden="true"
                    />
                    <span className="font-mono text-[12px]">{s}</span>
                    {target ? null : (
                      <span className="ml-1 text-[10px] uppercase tracking-wide text-neutral-500">
                        (no explainer yet)
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </article>
  );
}

export default function StrategyTemplateExplainerPage({ params }: PageProps) {
  const { slug } = use(params);
  const [lang, setLang] = useState<Lang>("hi");

  useEffect(() => {
    setLang(readLang());
  }, []);

  const handleLang = useCallback((next: Lang) => {
    setLang(next);
    writeLang(next);
  }, []);

  const explainer = getExplainer(slug);

  const titleCopy =
    lang === "hi"
      ? { back: "Templates wapas", title: "Strategy Explainer" }
      : { back: "Back to Templates", title: "Strategy Explainer" };

  // Display name: explainer.slug is kebab-case (e.g. "ema-crossover-9-21");
  // produce a readable form. Skip if no explainer.
  const displayName = explainer
    ? explainer.slug
        .split("-")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ")
    : slug;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      data-testid="explainer-page"
      data-slug={slug}
      className="mx-auto max-w-3xl space-y-5 p-4 md:p-6 lg:p-8"
    >
      {/* Header */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <Link
            href="/strategies/templates"
            data-testid="explainer-back-link"
            className="inline-flex items-center gap-1.5 text-xs text-neutral-400 hover:text-neutral-200"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            {titleCopy.back}
          </Link>
          <h1
            data-testid="explainer-page-title"
            className="text-2xl font-bold text-neutral-100"
          >
            {displayName}
          </h1>
          <p className="text-[11px] uppercase tracking-wide text-neutral-500">
            {titleCopy.title}
          </p>
        </div>
        <LangToggle lang={lang} onChange={handleLang} />
      </header>

      {/* Body */}
      {explainer ? (
        <ExplainerBody explainer={explainer} lang={lang} />
      ) : (
        <MissingExplainerFallback slug={slug} lang={lang} />
      )}
    </motion.div>
  );
}
