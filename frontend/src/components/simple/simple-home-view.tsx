"use client";

/**
 * Simple-mode home. PRESENTATIONAL: everything comes in as props so the design
 * can be reviewed (and screenshotted) with fixtures, and so the same view
 * renders in tests.
 *
 * Founder's call (2026-09-05, evening): NO LOCKS. Simplicity comes from ORDER
 * and plain words. Top: the four big tiles + status strip (the safety bar is
 * the shell's). Below: "Aur seekhein" — Templates dekho · Apni strategy banao
 * · Pro mode — all open, all tappable, one soft hint line. Then the journey
 * line (guidance), the day's lesson, and the quiet Pro card.
 *
 * Design bar: one memorable hero moment — a signal landing — brand green on
 * deep navy, glass-depth cards, big numbers, motion ONLY in answer to a real
 * event. 375px first.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { Landmark, Store, RadioTower, LifeBuoy, LayoutTemplate, Hammer, BookOpen, ChevronRight, BookMarked, LayoutGrid } from "lucide-react";
import type { Lang } from "@/contexts/LanguageContext";
import { t } from "@/lib/simple/copy";
import { TILE_ROUTE, type LearnTileId, type TileId, type UiLevel } from "@/lib/simple/level";
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

export interface SimpleProgress {
  done: number;
  total: number;
  /** The very next thing to do, in plain words. */
  next: string | null;
}

export interface SimpleHomeViewProps {
  lang: Lang;
  name: string;
  /** Guidance step (1–3) — shown as dots + a name, never a gate. */
  level: UiLevel;
  /** The four big tiles, in order. */
  mainTiles: TileId[];
  /** "Aur seekhein" — open tiles below the four. */
  learnTiles: LearnTileId[];
  /** First tap on an "Aur seekhein" tile (AlgoMitra's one line, once per tile). */
  onLearnTap: (id: LearnTileId) => void;
  /** One tap → Pro mode (full menu). */
  onOpenPro: () => void;
  brokerConnected: boolean;
  strategyRunning: boolean;
  learningMode: boolean;
  signalsToday: number;
  /** The latest signal, if one landed today — the hero moment. */
  latestSignal?: SimpleSignal | null;
  /** True when that signal is NEW since the last visit → it "lands". */
  signalIsNew?: boolean;
  lesson: SimpleLesson | null;
  progress: SimpleProgress;
}

const TILE_ICON: Record<TileId | "pro", typeof Store> = {
  strategy: Store,
  broker: Landmark,
  signals: RadioTower,
  help: LifeBuoy,
  templates: LayoutTemplate,
  build: Hammer,
  pro: LayoutGrid,
};

type TitleKey = "tile_strategy" | "tile_broker" | "tile_signals" | "tile_help" | "tile_templates" | "tile_build" | "tile_pro";
type SubKey = "tile_strategy_sub" | "tile_broker_sub" | "tile_signals_sub" | "tile_help_sub" | "tile_templates_sub" | "tile_build_sub" | "tile_pro_sub";

const TILE_COPY: Record<TileId | "pro", { title: TitleKey; sub: SubKey }> = {
  strategy: { title: "tile_strategy", sub: "tile_strategy_sub" },
  broker: { title: "tile_broker", sub: "tile_broker_sub" },
  signals: { title: "tile_signals", sub: "tile_signals_sub" },
  help: { title: "tile_help", sub: "tile_help_sub" },
  templates: { title: "tile_templates", sub: "tile_templates_sub" },
  build: { title: "tile_build", sub: "tile_build_sub" },
  pro: { title: "tile_pro", sub: "tile_pro_sub" },
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

const TILE_CLS = cn(
  "glass group relative flex flex-col justify-between gap-3 rounded-2xl p-4 md:p-5 min-h-[164px] md:min-h-[196px] w-full text-left",
  "border border-white/10 transition-[box-shadow,border-color,transform] duration-200",
  "active:scale-[0.98] hover:border-profit/50 hover:shadow-[0_0_28px_rgba(0,255,136,0.18)] focus-visible:border-profit focus-visible:outline-none",
);

function TileBody({ id, L }: { id: TileId | "pro"; L: (k: TitleKey | SubKey) => string }) {
  const Icon = TILE_ICON[id];
  return (
    <>
      <span className="inline-flex h-14 w-14 md:h-16 md:w-16 items-center justify-center rounded-2xl bg-profit/10 ring-1 ring-profit/25 group-hover:bg-profit/15 transition-colors">
        <Icon className="h-8 w-8 md:h-9 md:w-9 text-profit" aria-hidden="true" strokeWidth={1.75} />
      </span>
      <div>
        <p className="text-lg md:text-xl font-bold leading-tight text-foreground">{L(TILE_COPY[id].title)}</p>
        <p className="mt-1 text-xs md:text-sm text-muted-foreground leading-snug">{L(TILE_COPY[id].sub)}</p>
      </div>
      <ChevronRight className="absolute right-3 top-3 h-4 w-4 text-white/30 group-hover:text-profit transition-colors" aria-hidden="true" />
    </>
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

      {/* Greeting + journey step (guidance) */}
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[28px] md:text-[40px] font-extrabold tracking-tight leading-none text-foreground">
            {L("home_greeting", { name: p.name })}
          </h1>
          <p className="mt-2 text-sm md:text-base text-muted-foreground">{L("home_subtitle")}</p>
        </div>
        <div className="text-right shrink-0" data-testid="level-chip">
          <div className="flex items-center justify-end gap-1.5" aria-label={`step ${p.level} of 4`}>
            {[1, 2, 3, 4].map((n) => (
              <span
                key={n}
                aria-hidden="true"
                className={cn("h-1.5 rounded-full transition-all", n <= p.level ? "w-5 bg-profit" : "w-2 bg-white/15")}
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
          <p className="mt-0.5 text-4xl md:text-3xl font-extrabold tabular-nums leading-none text-foreground">{p.signalsToday}</p>
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
                    boxShadow: ["0 0 0 rgba(0,255,136,0)", "0 0 48px rgba(0,255,136,0.55)", "0 0 18px rgba(0,255,136,0.25)"],
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
              <p className="mt-1 text-3xl md:text-5xl font-extrabold tracking-tight text-foreground truncate">{p.latestSignal.symbol}</p>
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
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-muted-foreground">{L("signal_none_today")}</div>
        )}
      </section>

      {/* The four tiles — big, four across on desktop, two across on a phone */}
      <section className="mt-5 grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4" data-testid="tiles">
        {p.mainTiles.map((id) => (
          <Link key={id} href={TILE_ROUTE[id]} data-testid={`tile-${id}`} className={TILE_CLS}>
            <TileBody id={id} L={L} />
          </Link>
        ))}
      </section>

      {/* Journey line — guidance, never a gate */}
      <p className="mt-3 text-sm md:text-base text-muted-foreground" data-testid="progress-line">
        <span className="font-semibold text-foreground/85">{L("progress_line", { done: p.progress.done, total: p.progress.total })}</span>
        {p.progress.next ? <span> · {L("progress_next", { step: p.progress.next })}</span> : null}
      </p>

      {/* "Aur seekhein" — open from day one. One soft hint about order. */}
      <section className="mt-7" data-testid="learn-section">
        <h2 className="text-lg md:text-xl font-extrabold text-foreground">{L("learn_section_title")}</h2>
        <p className="mt-1 text-sm text-muted-foreground" data-testid="learn-hint">
          {L("learn_section_hint")}
        </p>
        <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-3 md:gap-4" data-testid="learn-tiles">
          {p.learnTiles.map((id) =>
            id === "pro" ? (
              <button
                key={id}
                type="button"
                data-testid="learn-pro"
                onClick={() => {
                  p.onLearnTap("pro");
                  p.onOpenPro();
                }}
                className={cn(TILE_CLS, "border-profit/30 bg-profit/[0.04]")}
              >
                <TileBody id="pro" L={L} />
              </button>
            ) : (
              <Link key={id} href={TILE_ROUTE[id]} data-testid={`learn-${id}`} onClick={() => p.onLearnTap(id)} className={TILE_CLS}>
                <TileBody id={id} L={L} />
              </Link>
            ),
          )}
        </div>
      </section>

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

      {/* A quiet way out for someone who already knows the way — Pro mode, one tap */}
      <button
        type="button"
        onClick={p.onOpenPro}
        data-testid="pro-entry"
        className="mt-6 w-full text-left rounded-2xl border border-white/10 bg-white/[0.02] px-4 py-4 md:px-5 hover:border-profit/40 transition-colors"
      >
        <span className="block text-base md:text-lg font-bold text-foreground">{L("pro_card_title")}</span>
        <span className="mt-1 block text-sm text-muted-foreground">{L("pro_card_body")}</span>
      </button>
    </div>
  );
}
