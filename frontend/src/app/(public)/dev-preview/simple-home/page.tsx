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
import { tilesForLevel, type UiLevel } from "@/lib/simple/level";
import type { Lang } from "@/contexts/LanguageContext";

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
