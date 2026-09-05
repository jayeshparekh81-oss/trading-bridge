"use client";

import { useEffect } from "react";

/**
 * The Simple-mode chrome (Level 1–3): no sidebar, no top bar. A slim header
 * (logo → home, level chip, language), the page, and the always-on safety bar.
 * The safety actions call endpoints that already exist:
 *   Rok do   — every active subscription → execution_mode "offline" (alerts
 *              only) and every own strategy → is_active false
 *   Sab band — POST /strategies/kill-switch (this account's open positions are
 *              closed and pending signals rejected), then the same pause
 *   Bahar    — useAuth().logout()
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Logo } from "@/components/logo";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLanguage } from "@/contexts/LanguageContext";
import { useLadder } from "@/hooks/useLadder";
import { t } from "@/lib/simple/copy";
import { SIMPLE_LANGS, ensureSimpleDefaultLanguage, mirrorLanguage } from "@/lib/simple/language-sync";
import { SafetyBar } from "@/components/simple/safety-bar";
import { cn } from "@/lib/utils";
import { ChevronLeft } from "lucide-react";

interface SubRow {
  id: string;
  status: string;
  execution_mode?: string | null;
}
interface StratRow {
  id: string;
  is_active?: boolean;
}

function list<T>(data: unknown, key: string): T[] {
  if (Array.isArray(data)) return data as T[];
  const v = data && typeof data === "object" ? (data as Record<string, unknown>)[key] : null;
  return Array.isArray(v) ? (v as T[]) : [];
}

export async function pauseEverything(): Promise<number> {
  let paused = 0;
  const subs = list<SubRow>(await api.get<unknown>("/marketplace/subscriptions/me").catch(() => null), "subscriptions");
  for (const s of subs) {
    if (s.status === "active" && s.execution_mode !== "offline") {
      await api.patch(`/marketplace/subscriptions/${s.id}/settings`, { execution_mode: "offline" }).catch(() => {});
      paused += 1;
    }
  }
  const strats = list<StratRow>(await api.get<unknown>("/strategies?limit=100").catch(() => null), "strategies");
  for (const s of strats) {
    if (s.is_active) {
      await api.patch(`/strategies/${s.id}/active`, { is_active: false }).catch(() => {});
      paused += 1;
    }
  }
  return paused;
}

export function SimpleShell({ children }: { children: ReactNode }) {
  const { logout } = useAuth();
  const { lang, setLang } = useLanguage();
  const ladder = useLadder();
  const pathname = usePathname();
  const isHome = pathname === "/";
  // Hinglish first for a customer who never chose (Levels 1–3 only).
  useEffect(() => ensureSimpleDefaultLanguage(setLang), [setLang]);

  async function onPause(): Promise<string> {
    const n = await pauseEverything();
    return n > 0 ? t(lang, "safety_paused_done") : t(lang, "safety_nothing_running");
  }

  async function onStopAll(): Promise<string> {
    await api.post("/strategies/kill-switch", {});
    await pauseEverything();
    return t(lang, "safety_stopped_done");
  }

  return (
    <div className="min-h-screen bg-background text-foreground" data-testid="simple-shell" data-level={ladder.level}>
      <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-[#0A0E1A]/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4 md:px-10">
          <div className="flex items-center gap-2 min-w-0">
            {!isHome ? (
              <Link
                href="/"
                data-testid="shell-home"
                className="inline-flex items-center gap-1 rounded-full border border-white/10 px-3 py-1.5 text-sm font-semibold text-foreground hover:border-profit/40"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                {t(lang, "shell_home")}
              </Link>
            ) : (
              <Link href="/" className="flex items-center gap-2" aria-label="TRADETRI">
                <Logo variant="icon" width={28} height={28} />
                <Logo variant="wordmark" height={20} />
              </Link>
            )}
          </div>
          <div className="flex items-center gap-2 md:mr-[300px]">
            <label className="sr-only" htmlFor="simple-lang">
              {t(lang, "lang_title")}
            </label>
            <select
              id="simple-lang"
              data-testid="simple-lang"
              value={lang}
              onChange={(e) => {
                const next = e.target.value as typeof lang;
                setLang(next);
                mirrorLanguage(next);
              }}
              className={cn(
                "rounded-full border border-white/10 bg-transparent px-3 py-1.5 text-sm font-medium text-foreground",
                "focus:outline-none focus-visible:border-profit",
              )}
            >
              {SIMPLE_LANGS.map((l) => (
                <option key={l.code} value={l.code} className="bg-[#0F1629] text-foreground">
                  {l.native}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>
      <main className="pb-28 md:pb-10">{children}</main>
      <SafetyBar lang={lang} onPause={onPause} onStopAll={onStopAll} onLogout={logout} />
    </div>
  );
}
