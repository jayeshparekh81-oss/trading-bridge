"use client";

/**
 * DEV-ONLY design preview of the Simple home with fixtures — never served in
 * production (404). ?level=1|2|3  ?lang=hinglish|hi|gu|en  ?signal=1|0
 */

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { SimpleHomeView } from "@/components/simple/simple-home-view";
import { SafetyBar } from "@/components/simple/safety-bar";
import { t } from "@/lib/simple/copy";
import { EMPTY_FACTS, LEARN_TILES, MAIN_TILES, type UiLevel } from "@/lib/simple/level";
import { buildProgress } from "@/lib/simple/journey";
import type { Lang } from "@/contexts/LanguageContext";

// Fixture facts per guidance step.
const FIX_FACTS: Record<number, typeof EMPTY_FACTS> = {
  1: { ...EMPTY_FACTS, hasSubscription: true },
  2: { ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true, firstSignalSeen: true },
  3: { ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true, firstSignalSeen: true, templateCloned: true, backtestRun: true },
  4: { ...EMPTY_FACTS },
};

function Inner() {
  const q = useSearchParams();
  const level = (Number(q.get("level") ?? 1) as UiLevel) || 1;
  const lang = (q.get("lang") ?? "hinglish") as Lang;
  const signal = q.get("signal") !== "0";
  return (
    <div className="min-h-screen bg-background text-foreground dark">
      <SimpleHomeView
        lang={lang}
        name="Ramesh"
        level={level}
        mainTiles={MAIN_TILES}
        learnTiles={LEARN_TILES}
        onLearnTap={() => {}}
        onOpenPro={() => {}}
        brokerConnected={level >= 2}
        strategyRunning={level >= 2}
        learningMode={level < 2}
        signalsToday={signal ? 3 : 0}
        latestSignal={signal ? { symbol: "BSE", sideLabel: t(lang, "side_buy"), price: "3,415.80", timeLabel: "13:15" } : null}
        signalIsNew={signal}
        lesson={{
          title: "Stop-loss kya hota hai?",
          body: "Stop-loss ek line hai jahan strategy khud nuksan rok deti hai — bina aapke phone uthaye. Har taiyar strategy mein yeh pehle se set hota hai.",
          href: "/help",
        }}
        progress={buildProgress(lang, level, FIX_FACTS[level])}
      />
      <SafetyBar lang={lang} onPause={async () => t(lang, "safety_paused_done")} onStopAll={async () => t(lang, "safety_stopped_done")} onLogout={() => {}} />
    </div>
  );
}

export default function PreviewSimpleHome() {
  return (
    <Suspense fallback={null}>
      <Inner />
    </Suspense>
  );
}
