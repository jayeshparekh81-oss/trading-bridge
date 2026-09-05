"use client";

/**
 * DEV-ONLY: the Simple chrome (header with "‹ Wapas" + safety bar) around the
 * home fixtures, so the confirm sheets can be reviewed at 375/1440. ?lang=…
 */

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { SimpleShell } from "@/components/simple/simple-shell";
import { SimpleHomeView } from "@/components/simple/simple-home-view";
import { EMPTY_FACTS, LEARN_TILES, MAIN_TILES } from "@/lib/simple/level";
import { buildProgress } from "@/lib/simple/journey";
import type { Lang } from "@/contexts/LanguageContext";

function Inner() {
  const q = useSearchParams();
  const lang = (q.get("lang") ?? "hinglish") as Lang;
  return (
    <SimpleShell>
      <SimpleHomeView
        lang={lang}
        name="Ramesh"
        level={1}
        mainTiles={MAIN_TILES}
        learnTiles={LEARN_TILES}
        onLearnTap={() => {}}
        onOpenPro={() => {}}
        brokerConnected={false}
        strategyRunning={false}
        learningMode={true}
        signalsToday={0}
        latestSignal={null}
        signalIsNew={false}
        lesson={{ title: "Stop-loss kya hota hai?", body: "Stop-loss ek line hai jahan strategy khud nuksan rok deti hai — bina aapke phone uthaye.", href: "/help" }}
        progress={buildProgress(lang, 1, EMPTY_FACTS)}
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
