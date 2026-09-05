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
import { tilesForLevel } from "@/lib/simple/level";
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
