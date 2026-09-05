"use client";

/**
 * Simple home CONTAINER — wires the presentational view to real data: status
 * (useSimpleStatus), the mode/journey state (useLadder), the day's lesson,
 * and AlgoMitra's two one-liners: the first-visit nudge, and the first tap on
 * an "Aur seekhein" tile. The hero "signal landing" fires only when a signal
 * is NEW since the last visit (remembered per browser), never on every render.
 *
 * Nothing here gates anything (founder, 2026-09-05 evening).
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
import { LEARN_TILES, MAIN_TILES, factFlags, type LearnTileId } from "@/lib/simple/level";
import { buildProgress, tipFor } from "@/lib/simple/journey";
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

export function SimpleHome() {
  const { user } = useAuth();
  const { lang } = useLanguage();
  const ladder = useLadder();
  const router = useRouter();
  const status = useSimpleStatus(true);

  // Server-derived facts → the journey line (credits things done in Pro / elsewhere).
  const factsJson = JSON.stringify(status.facts);
  useEffect(() => {
    if (!status.loading && Object.keys(status.facts).length) ladder.observe(status.facts);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [factsJson, status.loading]);

  // The hero: is the latest signal new since the last visit?
  const latest = status.latestSignal;
  const [lastSeenId] = useState<string>(() => readLastSignal() ?? "");
  const signalIsNew = !!latest && lastSeenId !== latest.id;
  useEffect(() => {
    if (latest) writeLastSignal(latest.id);
  }, [latest]);

  const heroSignal: SimpleSignal | null = useMemo(() => {
    if (!latest) return null;
    const side = (latest.side ?? "").toLowerCase();
    const isExit = /exit|sl_hit|partial/i.test(latest.action ?? "");
    const sideLabel = isExit ? t(lang, "signal_exit") : side === "sell" || side === "short" ? t(lang, "side_sell") : t(lang, "side_buy");
    const price = latest.entry ? Number(latest.entry).toLocaleString("en-IN", { maximumFractionDigits: 2 }) : null;
    const timeLabel = new Date(latest.received_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" });
    return { symbol: latest.symbol, sideLabel, price, timeLabel };
  }, [latest, lang]);

  const level = ladder.level;
  const facts = factFlags(ladder.state?.facts);
  const progress = buildProgress(lang, level, facts);

  // One tap → Pro: the full menu, with the expanded-sidebar nudge shown once.
  const openPro = async () => {
    await ladder.setChoice("pro");
    toast.success(t(lang, "settings_mode_saved"));
    router.push("/");
  };

  // First tap on an "Aur seekhein" tile: AlgoMitra explains it in one line, once per tile.
  const onLearnTap = (id: LearnTileId) => {
    if (ladder.state?.tipsShown?.includes(id)) return;
    toast.info(tipFor(lang, id), { duration: 6000 });
    ladder.markTipShown(id);
  };

  // First Simple-home visit: AlgoMitra says how the home works, once per account.
  const homeNudged = useRef(false);
  const homeNudgeSeen = ladder.state ? !!ladder.state.homeNudgeSeen : true;
  useEffect(() => {
    if (!ladder.ready || homeNudgeSeen || homeNudged.current) return;
    if (!languageSettled(lang)) return;
    homeNudged.current = true;
    toast.info(`${t(lang, "nudge_prefix")}: ${t(lang, "nudge_home_first")}`, { duration: 9000 });
    ladder.markHomeNudgeSeen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ladder.ready, homeNudgeSeen, lang]);

  const lesson = useMemo(() => lessonForDay(new Date(), lang), [lang]);
  const name = user?.full_name?.split(" ")[0] || user?.email?.split("@")[0] || "";

  return (
    <SimpleHomeView
      lang={lang}
      name={name}
      level={level}
      mainTiles={MAIN_TILES}
      learnTiles={LEARN_TILES}
      onLearnTap={onLearnTap}
      onOpenPro={openPro}
      brokerConnected={status.brokerConnected}
      strategyRunning={status.strategyRunning}
      learningMode={status.learningMode}
      signalsToday={status.signalsToday}
      latestSignal={heroSignal}
      signalIsNew={signalIsNew}
      lesson={lesson}
      progress={progress}
    />
  );
}
