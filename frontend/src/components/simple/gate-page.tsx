"use client";

/**
 * The friendly level gate (C9). A lower-level customer who lands on a
 * higher-level route by URL sees this — never an error, never a redirect
 * (no redirect means no loop): "Yeh aage khulega — ya Settings se Pro on karo".
 */

import Link from "next/link";
import { Lock } from "lucide-react";
import type { Lang } from "@/contexts/LanguageContext";
import { t } from "@/lib/simple/copy";
import type { UiLevel } from "@/lib/simple/level";

export function GatePage({ lang, needed, level }: { lang: Lang; needed: UiLevel; level: UiLevel }) {
  const hint =
    needed === 2
      ? t(lang, "unlock_next_hint_level2")
      : needed === 3
        ? t(lang, "unlock_next_hint_level3")
        : t(lang, "unlock_next_hint_level4");
  return (
    <div
      className="min-h-[70vh] flex items-center justify-center px-4 py-10"
      data-testid="level-gate"
      data-needed={needed}
      data-level={level}
    >
      <div className="glass w-full max-w-md rounded-3xl border border-white/10 p-6 md:p-8 text-center">
        <span className="mx-auto inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-profit/10 ring-1 ring-profit/25">
          <Lock className="h-8 w-8 text-profit" aria-hidden="true" />
        </span>
        <h1 className="mt-4 text-2xl font-extrabold text-foreground">{t(lang, "gate_title")}</h1>
        <p className="mt-2 text-sm text-foreground/80">{t(lang, "gate_body")}</p>
        <p className="mt-3 text-xs text-muted-foreground">{hint}</p>
        <div className="mt-6 flex flex-col gap-2">
          <Link
            href="/"
            data-testid="gate-home"
            className="inline-flex items-center justify-center rounded-full bg-profit px-5 py-3 text-base font-bold text-[#0A0E1A]"
          >
            {t(lang, "gate_home")}
          </Link>
          <Link
            href="/settings#mode"
            data-testid="gate-pro"
            className="inline-flex items-center justify-center rounded-full border border-white/15 px-5 py-3 text-base font-semibold text-foreground"
          >
            {t(lang, "gate_pro")}
          </Link>
        </div>
      </div>
    </div>
  );
}
