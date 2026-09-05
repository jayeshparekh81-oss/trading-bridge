"use client";

/**
 * Simple home CONTAINER — wires the presentational view to real data:
 * status (useSimpleStatus), the ladder (useLadder), the day's lesson, the
 * language switch, and the two announcements an unlock triggers (home card +
 * an AlgoMitra nudge). The hero "signal landing" fires only when a signal is
 * NEW since the last visit (remembered per browser), never on every render.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { useLanguage } from "@/contexts/LanguageContext";
import { useLadder } from "@/hooks/useLadder";
import { useSimpleStatus } from "@/hooks/useSimpleStatus";
import { lessonForDay } from "@/lib/simple/lessons";
import { t } from "@/lib/simple/copy";
import { TILE_ROUTE, factFlags, tilesForLevel, type TileId, type UiLevel } from "@/lib/simple/level";
import { buildLocked, buildProgress } from "@/lib/simple/locks";
import { SimpleHomeView, type SimpleSignal } from "@/components/simple/simple-home-view";

const LAST_SIGNAL_KEY = "tradetri_simple_last_signal";

function readLastSignal(): string | null {
  try {
    return window.localStorage.getItem(LAST_SIGNAL_KEY);
  } catch {
    return null;
  }
}

function writeLastSignal(id: string): void {
  try {
    window.localStorage.setItem(LAST_SIGNAL_KEY, id);
  } catch {
    // ignore
  }
}

/** True once the language the provider renders with IS the stored choice
 *  (a first visit is flipped to Hinglish by the shell one render after mount). */
function languageSettled(lang: string): boolean {
  try {
    return window.localStorage.getItem("tradetri_language") === lang;
  } catch {
    return true;
  }
}

function unlockTile(level: UiLevel): TileId {
  return level >= 3 ? "build" : "templates";
}

export function SimpleHome() {
  const { user } = useAuth();
  const { lang } = useLanguage();
  const ladder = useLadder();
  const router = useRouter();
  const status = useSimpleStatus(true);

  // Server-derived facts → the ladder (credits things done in Pro / elsewhere).
  const factsJson = JSON.stringify(status.facts);
  useEffect(() => {
    if (!status.loading && Object.keys(status.facts).length) ladder.observe(status.facts);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [factsJson, status.loading]);

  // The hero: is the latest signal new since the last visit?
  const latest = status.latestSignal;
  // What the customer had already seen when this page mounted (localStorage);
  // read once, lazily, so a signal that lands later stays "new" this visit.
  const [lastSeenId] = useState<string>(() => readLastSignal() ?? "");
  const signalIsNew = !!latest && lastSeenId !== latest.id;
  useEffect(() => {
    if (latest) writeLastSignal(latest.id);
  }, [latest]);

  const heroSignal: SimpleSignal | null = useMemo(() => {
    if (!latest) return null;
    const side = (latest.side ?? "").toLowerCase();
    const isExit = /exit|sl_hit|partial/i.test(latest.action ?? "");
    const sideLabel = isExit
      ? t(lang, "signal_exit")
      : side === "sell" || side === "short"
        ? t(lang, "side_sell")
        : t(lang, "side_buy");
    const price = latest.entry ? Number(latest.entry).toLocaleString("en-IN", { maximumFractionDigits: 2 }) : null;
    const timeLabel = new Date(latest.received_at).toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Kolkata",
    });
    return { symbol: latest.symbol, sideLabel, price, timeLabel };
  }, [latest, lang]);

  // Unlock announcement: the home card + one AlgoMitra nudge (toast), once.
  const pending = ladder.pendingUnlock;
  const nudged = useRef<UiLevel | null>(null);
  useEffect(() => {
    if (!pending || nudged.current === pending) return;
    nudged.current = pending;
    const why = t(lang, pending === 2 ? "unlock_level2_why" : pending === 3 ? "unlock_level3_why" : "unlock_level4_why");
    toast.success(`${t(lang, "nudge_prefix")}: ${why}`, { duration: 6000 });
  }, [pending, lang]);

  const level = ladder.level;
  const tiles = tilesForLevel(level);

  // Locked tiles are VISIBLE (game levels): each says, in one line, what opens
  // it — computed from the customer's ACTUAL facts, so a Pro account that
  // switched to Simple sees what it has really done, not a fresh-account zero.
  const facts = factFlags(ladder.state?.facts);
  const locked = buildLocked(lang, level, facts);
  const progress = buildProgress(lang, level, facts);

  // One tap → Pro: the full menu, with the expanded-sidebar nudge shown once.
  const openPro = async () => {
    await ladder.setChoice("pro");
    toast.success(t(lang, "settings_mode_saved"));
    router.push("/");
  };

  // First Simple-home visit: AlgoMitra says how the ladder works, once per account.
  const homeNudged = useRef(false);
  // A fresh state has no flag at all — that means NOT seen (the walk caught `?? true` treating it as seen).
  const homeNudgeSeen = ladder.state ? !!ladder.state.homeNudgeSeen : true;
  useEffect(() => {
    if (!ladder.ready || homeNudgeSeen || homeNudged.current) return;
    // Wait for the language to be settled (a first visit is flipped to Hinglish
    // by the shell one render after mount) — otherwise the nudge fires in the
    // provider's English default.
    if (!languageSettled(lang)) return;
    homeNudged.current = true;
    toast.info(`${t(lang, "nudge_prefix")}: ${t(lang, "nudge_home_first")}`, { duration: 9000 });
    ladder.markHomeNudgeSeen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ladder.ready, homeNudgeSeen, lang]);
  const lesson = useMemo(() => lessonForDay(new Date(), lang), [lang]);
  const name = user?.full_name?.split(" ")[0] || user?.email?.split("@")[0] || "";

  const nextHint =
    level === 1
      ? t(lang, "unlock_next_hint_level2")
      : level === 2
        ? t(lang, "unlock_next_hint_level3")
        : level === 3
          ? t(lang, "unlock_next_hint_level4")
          : null;

  return (
    <SimpleHomeView
      lang={lang}
      name={name}
      level={level}
      tiles={tiles}
      locked={locked}
      progress={progress}
      onOpenPro={openPro}
      justUnlocked={pending ? unlockTile(pending) : null}
      brokerConnected={status.brokerConnected}
      strategyRunning={status.strategyRunning}
      learningMode={status.learningMode}
      signalsToday={status.signalsToday}
      latestSignal={heroSignal}
      signalIsNew={signalIsNew}
      lesson={lesson}
      unlock={
        pending
          ? {
              level: pending,
              why: t(lang, pending === 2 ? "unlock_level2_why" : pending === 3 ? "unlock_level3_why" : "unlock_level4_why"),
              href: pending === 4 ? "/settings#mode" : TILE_ROUTE[unlockTile(pending)],
              onDismiss: () => ladder.announce(pending),
              secondary:
                pending === 2
                  ? {
                      label: t(lang, "unlock_walkthrough_cta"),
                      onClick: () => {
                        // AlgoMitra's chat widget listens for this (see ChatWidget).
                        window.dispatchEvent(
                          new CustomEvent("algomitra:open", { detail: { prompt: t(lang, "nudge_walkthrough") } }),
                        );
                        toast(t(lang, "nudge_walkthrough"), { duration: 5000 });
                      },
                    }
                  : undefined,
            }
          : null
      }
      nextHint={nextHint}
    />
  );
}
