"use client";

/** DEV-ONLY: the Level gate page with fixtures. ?needed=2|3|4 ?level=1|2|3 ?lang=… */

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { GatePage } from "@/components/simple/gate-page";
import type { UiLevel } from "@/lib/simple/level";
import type { Lang } from "@/contexts/LanguageContext";

function Inner() {
  const q = useSearchParams();
  return (
    <div className="min-h-screen bg-background text-foreground dark">
      <GatePage
        lang={(q.get("lang") ?? "hinglish") as Lang}
        needed={(Number(q.get("needed") ?? 4) as UiLevel) || 4}
        level={(Number(q.get("level") ?? 1) as UiLevel) || 1}
      />
    </div>
  );
}

export default function PreviewGate() {
  return (
    <Suspense fallback={null}>
      <Inner />
    </Suspense>
  );
}
