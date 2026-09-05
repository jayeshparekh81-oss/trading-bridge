"use client";

/**
 * DEV-ONLY: the Simple chrome (header + safety bar) around the home fixtures,
 * so the confirm sheets can be reviewed at 375/1440. ?lang=…
 */

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { SimpleShell } from "@/components/simple/simple-shell";
import { SimpleHomeView } from "@/components/simple/simple-home-view";
import { t } from "@/lib/simple/copy";
import { EMPTY_FACTS, tilesForLevel } from "@/lib/simple/level";
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
  const lang = (q.get("lang") ?? "hinglish") as Lang;
  const level = 1 as const;
  return (
    <SimpleShell>
      <SimpleHomeView
        lang={lang}
        name="Ramesh"
        level={1}
        locked={buildLocked(lang, level, FIX_FACTS[level])}
        progress={buildProgress(lang, level, FIX_FACTS[level])}
        onOpenPro={() => {}}
        tiles={tilesForLevel(1)}
        justUnlocked={null}
        brokerConnected={false}
        strategyRunning={false}
        learningMode={true}
        signalsToday={0}
        latestSignal={null}
        signalIsNew={false}
        lesson={{ title: "Stop-loss kya hota hai?", body: "Stop-loss ek line hai jahan strategy khud nuksan rok deti hai — bina aapke phone uthaye.", href: "/help" }}
        unlock={null}
        nextHint={t(lang, "unlock_next_hint_level2")}
      />
    </SimpleShell>
  );
}

export default function PreviewShell() {
  return (
    <Suspense fallback={null}>
      <Inner />
    </Suspense>
  );
}
