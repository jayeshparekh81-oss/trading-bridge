"use client";

/**
 * Simple-mode home — Level 1–3. PRESENTATIONAL: everything comes in as props so
 * the design can be reviewed (and screenshotted) with fixtures before any data
 * is wired, and so the same view renders in tests.
 *
 * Design bar (founder 2026-09-05): one memorable hero moment — a signal
 * landing — brand green on deep navy, glass-depth cards, big numbers, motion
 * ONLY in answer to the user's action or a real event (a signal arriving, a
 * tile unlocking). No decoration for its own sake. 375px first.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import {
  Landmark,
  Store,
  RadioTower,
  LifeBuoy,
  LayoutTemplate,
  Hammer,
  BookOpen,
  ChevronRight,
  BookMarked,
  Sparkles,
} from "lucide-react";
import type { Lang } from "@/contexts/LanguageContext";
import { t } from "@/lib/simple/copy";
import { TILE_ROUTE, TILE_LEVEL, type TileId, type UiLevel } from "@/lib/simple/level";
import { cn } from "@/lib/utils";

export interface SimpleSignal {
  symbol: string;
  /** Plain-words side, already translated ("Kharida" / "Becha"). */
  sideLabel: string;
  price: string | null;
  timeLabel: string;
}

export interface SimpleLesson {
  title: string;
  body: string;
  href: string;
}

export interface SimpleHomeViewProps {
  lang: Lang;
  name: string;
  level: UiLevel;
  tiles: TileId[];
  /** Tile that JUST unlocked — gets the one-time celebration. */
  justUnlocked?: TileId | null;
  brokerConnected: boolean;
  strategyRunning: boolean;
  learningMode: boolean;
  signalsToday: number;
  /** The latest signal, if one landed today — the hero moment. */
  latestSignal?: SimpleSignal | null;
  /** True when that signal is NEW since the last visit → it "lands". */
  signalIsNew?: boolean;
  lesson: SimpleLesson | null;
  unlock?: {
    level: UiLevel;
    why: string;
    href: string;
    onDismiss: () => void;
    /** Optional second action, e.g. the Level-2 AlgoMitra two-minute tour. */
    secondary?: { label: string; onClick: () => void };
  } | null;
  nextHint?: string | null;
}

const TILE_ICON: Record<TileId, typeof Store> = {
  strategy: Store,
  broker: Landmark,
  signals: RadioTower,
  help: LifeBuoy,
  templates: LayoutTemplate,
  build: Hammer,
  learn: BookOpen,
};

const TILE_COPY: Record<TileId, { title: "tile_strategy" | "tile_broker" | "tile_signals" | "tile_help" | "tile_templates" | "tile_build" | "tile_learn_indicators"; sub: "tile_strategy_sub" | "tile_broker_sub" | "tile_signals_sub" | "tile_help_sub" | "tile_templates_sub" | "tile_build_sub" | "tile_learn_indicators_sub" }> = {
  strategy: { title: "tile_strategy", sub: "tile_strategy_sub" },
  broker: { title: "tile_broker", sub: "tile_broker_sub" },
  signals: { title: "tile_signals", sub: "tile_signals_sub" },
  help: { title: "tile_help", sub: "tile_help_sub" },
  templates: { title: "tile_templates", sub: "tile_templates_sub" },
  build: { title: "tile_build", sub: "tile_build_sub" },
  learn: { title: "tile_learn_indicators", sub: "tile_learn_indicators_sub" },
};

function Dot({ on }: { on: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block h-2.5 w-2.5 rounded-full shrink-0",
        on ? "bg-profit shadow-[0_0_10px_rgba(0,255,136,0.7)]" : "bg-white/20",
      )}
    />
  );
}

export function SimpleHomeView(p: SimpleHomeViewProps) {
  const reduce = useReducedMotion();
  const L = (k: Parameters<typeof t>[1], vars?: Record<string, string | number>) => t(p.lang, k, vars);

  return (
    <div
      className="relative min-h-full px-4 pt-6 pb-28 md:px-10 md:pt-10 md:pb-12 max-w-6xl mx-auto"
      data-testid="simple-home"
      data-level={p.level}
    >
      {/* The canvas: deep navy with one soft brand-green glow. Static. */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60% 40% at 15% 0%, rgba(0,255,136,0.10) 0%, rgba(0,255,136,0) 60%), #0A0E1A",
        }}
      />

      {/* Greeting + level */}
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[28px] md:text-[40px] font-extrabold tracking-tight leading-none text-foreground">
            {L("home_greeting", { name: p.name })}
          </h1>
          <p className="mt-2 text-sm md:text-base text-muted-foreground">{L("home_subtitle")}</p>
        </div>
        <div className="text-right shrink-0" data-testid="level-chip">
          <div className="flex items-center justify-end gap-1.5" aria-label={`level ${p.level} of 4`}>
            {[1, 2, 3, 4].map((n) => (
              <span
                key={n}
                aria-hidden="true"
                className={cn(
                  "h-1.5 rounded-full transition-all",
                  n <= p.level ? "w-5 bg-profit" : "w-2 bg-white/15",
                )}
              />
            ))}
          </div>
          <p className="mt-1 text-[11px] uppercase tracking-[0.18em] text-profit/90 font-mono">
            {L(`level${p.level}_name` as "level1_name")}
          </p>
        </div>
      </header>

      {/* Status strip — three facts, plain words, one glass card. On a phone
          the two yes/no facts stack as rows so nothing truncates; the count
          stays the big number on the right. */}
      <section
        className="glass mt-6 rounded-2xl p-4 md:p-5 flex flex-wrap items-stretch gap-4 md:grid md:grid-cols-3 md:gap-3"
        data-testid="status-strip"
        aria-label="status"
      >
        <div className="flex-1 min-w-0 space-y-3 md:contents">
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{L("status_broker")}</p>
            <p className="mt-1 flex items-center gap-2 text-[15px] md:text-base font-semibold">
              <Dot on={p.brokerConnected} />
              <span className="truncate">{p.brokerConnected ? L("status_broker_yes") : L("status_broker_no")}</span>
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{L("status_strategy")}</p>
            <p className="mt-1 flex items-center gap-2 text-[15px] md:text-base font-semibold">
              <Dot on={p.strategyRunning} />
              <span className="truncate">{p.strategyRunning ? L("status_strategy_yes") : L("status_strategy_no")}</span>
            </p>
          </div>
        </div>
        <div className="shrink-0 text-right md:text-left border-l border-white/10 pl-4 md:border-0 md:pl-0 flex flex-col justify-center">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{L("status_signals")}</p>
          <p className="mt-0.5 text-4xl md:text-3xl font-extrabold tabular-nums leading-none text-foreground">
            {p.signalsToday}
          </p>
        </div>
        {p.learningMode && (
          <p
            className="basis-full md:col-span-3 inline-flex items-center gap-1.5 self-start rounded-full border border-accent-gold/30 bg-accent-gold/10 px-2.5 py-1 text-[11px] text-accent-gold"
            data-testid="learning-mode"
          >
            <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />
            {L("status_learning_mode")}
          </p>
        )}
      </section>

      {/* Unlock announcement — only when something NEW opened */}
      {p.unlock && (
        <motion.section
          initial={reduce ? false : { opacity: 0, y: 12, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="mt-4 rounded-2xl border border-profit/40 bg-profit/10 p-4 md:p-5 flex items-start gap-3"
          data-testid="unlock-card"
        >
          <Sparkles className="h-6 w-6 text-profit shrink-0 mt-0.5" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-base md:text-lg font-bold text-foreground">{L("unlock_title")}</p>
            <p className="mt-1 text-sm text-foreground/85">{p.unlock.why}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                href={p.unlock.href}
                className="inline-flex items-center rounded-full bg-profit px-4 py-2 text-sm font-bold text-[#0A0E1A]"
              >
                {L("unlock_cta")}
              </Link>
              {p.unlock.secondary && (
                <button
                  type="button"
                  data-testid="unlock-secondary"
                  onClick={p.unlock.secondary.onClick}
                  className="inline-flex items-center rounded-full border border-profit/50 px-4 py-2 text-sm font-bold text-profit"
                >
                  {p.unlock.secondary.label}
                </button>
              )}
              <button
                type="button"
                onClick={p.unlock.onDismiss}
                className="inline-flex items-center rounded-full px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground"
              >
                {L("unlock_later")}
              </button>
            </div>
          </div>
        </motion.section>
      )}

      {/* THE HERO MOMENT — a signal landing */}
      <section className="mt-4" data-testid="hero-signal">
        {p.latestSignal ? (
          <motion.div
            key={`${p.latestSignal.symbol}-${p.latestSignal.timeLabel}`}
            initial={p.signalIsNew && !reduce ? { opacity: 0, y: 24, scale: 0.97 } : false}
            animate={
              p.signalIsNew && !reduce
                ? {
                    opacity: 1,
                    y: 0,
                    scale: 1,
                    boxShadow: [
                      "0 0 0 rgba(0,255,136,0)",
                      "0 0 48px rgba(0,255,136,0.55)",
                      "0 0 18px rgba(0,255,136,0.25)",
                    ],
                  }
                : { opacity: 1 }
            }
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            className="rounded-2xl border border-profit/50 bg-[#0F1629] p-5 md:p-6 flex items-center justify-between gap-4"
          >
            <div className="min-w-0">
              <p className="text-[11px] uppercase tracking-[0.18em] text-profit font-mono">
                {L("signal_landed")} · {p.latestSignal.timeLabel}
              </p>
              <p className="mt-1 text-3xl md:text-5xl font-extrabold tracking-tight text-foreground truncate">
                {p.latestSignal.symbol}
              </p>
              <p className="mt-1 text-lg md:text-2xl font-bold text-profit">{p.latestSignal.sideLabel}</p>
              {p.latestSignal.price ? (
                <p className="text-xl md:text-2xl font-semibold tabular-nums text-foreground/85">₹{p.latestSignal.price}</p>
              ) : null}
            </div>
            <Link
              href={TILE_ROUTE.signals}
              className="shrink-0 inline-flex items-center gap-1 rounded-full border border-profit/40 px-3 py-2 text-sm font-semibold text-profit"
            >
              {L("signal_see_all")} <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </motion.div>
        ) : (
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-muted-foreground">
            {L("signal_none_today")}
          </div>
        )}
      </section>

      {/* The tiles — big, four across on desktop, two across on a phone */}
      <section className="mt-5 grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4" data-testid="tiles">
        {p.tiles.map((id) => {
          const Icon = TILE_ICON[id];
          const isNew = p.justUnlocked === id;
          return (
            <motion.div
              key={id}
              initial={isNew && !reduce ? { opacity: 0, scale: 0.9 } : false}
              animate={isNew && !reduce ? { opacity: 1, scale: [0.9, 1.04, 1] } : { opacity: 1 }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            >
              <Link
                href={TILE_ROUTE[id]}
                data-testid={`tile-${id}`}
                data-tile-level={TILE_LEVEL[id]}
                className={cn(
                  "glass group relative flex flex-col justify-between gap-3 rounded-2xl p-4 md:p-5 min-h-[164px] md:min-h-[196px]",
                  "border border-white/10 transition-[box-shadow,border-color,transform] duration-200",
                  "active:scale-[0.98] hover:border-profit/50 hover:shadow-[0_0_28px_rgba(0,255,136,0.18)] focus-visible:border-profit focus-visible:outline-none",
                  isNew && "border-profit/60 shadow-[0_0_36px_rgba(0,255,136,0.30)]",
                )}
              >
                <span className="inline-flex h-14 w-14 md:h-16 md:w-16 items-center justify-center rounded-2xl bg-profit/10 ring-1 ring-profit/25 group-hover:bg-profit/15 transition-colors">
                  <Icon className="h-8 w-8 md:h-9 md:w-9 text-profit" aria-hidden="true" strokeWidth={1.75} />
                </span>
                <div>
                  <p className="text-lg md:text-xl font-bold leading-tight text-foreground">
                    {L(TILE_COPY[id].title)}
                  </p>
                  <p className="mt-1 text-xs md:text-sm text-muted-foreground leading-snug">
                    {L(TILE_COPY[id].sub)}
                  </p>
                </div>
                <ChevronRight
                  className="absolute right-3 top-3 h-4 w-4 text-white/30 group-hover:text-profit transition-colors"
                  aria-hidden="true"
                />
              </Link>
            </motion.div>
          );
        })}
      </section>

      {p.nextHint && (
        <p className="mt-3 text-[12px] text-muted-foreground" data-testid="next-hint">
          {p.nextHint}
        </p>
      )}

      {/* Aaj ka sabak — one learning card a day */}
      {p.lesson && (
        <section className="glass mt-5 rounded-2xl p-4 md:p-5 flex gap-3" data-testid="lesson-card">
          <BookMarked className="h-6 w-6 text-accent-gold shrink-0 mt-0.5" aria-hidden="true" />
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-[0.18em] text-accent-gold font-mono">{L("lesson_title")}</p>
            <p className="mt-1 text-base md:text-lg font-bold text-foreground">{p.lesson.title}</p>
            <p className="mt-1 text-sm text-foreground/80 line-clamp-3">{p.lesson.body}</p>
            <Link href={p.lesson.href} className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-profit">
              {L("lesson_more")} <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}
