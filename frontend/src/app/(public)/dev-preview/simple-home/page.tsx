"use client";

/**
 * DEV-ONLY design preview of the Simple home with fixtures — never served in
 * production (404). Lets the Level-1 home be reviewed at 375/1440 before any
 * data is wired. ?level=1|2|3  ?lang=hinglish|hi|gu|en  ?signal=1|0  ?unlock=1
 */

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { SimpleHomeView } from "@/components/simple/simple-home-view";
import { SafetyBar } from "@/components/simple/safety-bar";
import { t } from "@/lib/simple/copy";
import { EMPTY_FACTS, tilesForLevel, type UiLevel } from "@/lib/simple/level";
import { buildLocked, buildProgress } from "@/lib/simple/locks";
import type { Lang } from "@/contexts/LanguageContext";

// Fixture facts per level: L1 has subscribed only (so the L2 hint names the two
// missing steps), L2 has everything for L2, L3 has cloned + tested.
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
  const unlock = q.get("unlock") === "1";
  return (
    <div className="min-h-screen bg-background text-foreground dark">
      <SimpleHomeView
        lang={lang}
        name="Ramesh"
        level={level}
        locked={buildLocked(lang, level, FIX_FACTS[level])}
        progress={buildProgress(lang, level, FIX_FACTS[level])}
        onOpenPro={() => {}}
        tiles={tilesForLevel(level)}
        justUnlocked={unlock ? (level >= 3 ? "build" : "templates") : null}
        brokerConnected={level >= 2}
        strategyRunning={level >= 2}
        learningMode={level < 2}
        signalsToday={signal ? 3 : 0}
        latestSignal={signal ? { symbol: "BSE", sideLabel: t(lang, "unlock_cta") === "Dekho" ? "Kharida" : "Bought", price: "3,415.80", timeLabel: "13:15" } : null}
        signalIsNew={signal}
        lesson={{
          title: "Stop-loss kya hota hai?",
          body: "Stop-loss ek line hai jahan strategy khud nuksan rok deti hai — bina aapke phone uthaye. Har taiyar strategy mein yeh pehle se set hota hai.",
          href: "/help",
        }}
        unlock={
          unlock
            ? {
                level: level >= 3 ? 3 : 2,
                why: t(lang, level >= 3 ? "unlock_level3_why" : "unlock_level2_why"),
                href: "/strategies/templates",
                onDismiss: () => {},
                secondary: level < 3 ? { label: t(lang, "unlock_walkthrough_cta"), onClick: () => {} } : undefined,
              }
            : null
        }
        nextHint={t(lang, level === 1 ? "unlock_next_hint_level2" : level === 2 ? "unlock_next_hint_level3" : "unlock_next_hint_level4")}
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
