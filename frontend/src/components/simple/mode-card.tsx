"use client";

/**
 * Settings → Mode: Simple ⇄ Pro + language. Choosing a mode LANDS the customer
 * on the home of that mode immediately (router.push("/")) — switching must
 * never end on a page whose chrome just changed under them (the Settings dead
 * end the founder hit). Switching into Pro also shows the expanded-sidebar
 * nudge once (useLadder.setChoice resets proNudgeSeen).
 */

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Layers, Languages } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useLanguage } from "@/contexts/LanguageContext";
import { useLadder } from "@/hooks/useLadder";
import { t } from "@/lib/simple/copy";
import { SIMPLE_LANGS, mirrorLanguage } from "@/lib/simple/language-sync";
import { cn } from "@/lib/utils";

export function ModeCard() {
  const ladder = useLadder();
  const { lang, setLang } = useLanguage();
  const router = useRouter();

  async function choose(m: "simple" | "pro") {
    await ladder.setChoice(m);
    toast.success(t(lang, "settings_mode_saved"));
    router.push("/");
  }

  return (
    <section id="mode" data-testid="mode-card">
      <GlassmorphismCard className="p-5 space-y-4">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
          <Layers className="h-4 w-4" /> {t(lang, "settings_mode_title")}
        </h2>
        <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label={t(lang, "settings_mode_title")}>
          {(["simple", "pro"] as const).map((m) => {
            const active = m === "pro" ? ladder.level === 4 : ladder.level < 4;
            return (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={active}
                data-testid={`mode-${m}`}
                onClick={() => void choose(m)}
                className={cn(
                  "rounded-2xl border px-4 py-3 text-base font-semibold transition-colors",
                  active ? "border-profit bg-profit/10 text-foreground" : "border-white/10 text-foreground/80 hover:border-profit/40",
                )}
              >
                {m === "pro" ? t(lang, "settings_mode_pro") : t(lang, "settings_mode_simple")}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground">{t(lang, "settings_mode_help")}</p>
        <div className="pt-2 border-t border-white/[0.06]">
          <label htmlFor="settings-lang" className="text-sm font-medium flex items-center gap-2">
            <Languages className="h-4 w-4 text-muted-foreground" /> {t(lang, "lang_title")}
          </label>
          <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2" id="settings-lang" data-testid="settings-lang">
            {SIMPLE_LANGS.map((l) => (
              <button
                key={l.code}
                type="button"
                data-testid={`settings-lang-${l.code}`}
                onClick={() => {
                  setLang(l.code);
                  mirrorLanguage(l.code);
                }}
                className={cn(
                  "rounded-xl border px-3 py-2 text-sm font-semibold transition-colors",
                  lang === l.code ? "border-profit bg-profit/10 text-foreground" : "border-white/10 text-foreground/80 hover:border-profit/40",
                )}
              >
                {l.native}
              </button>
            ))}
          </div>
        </div>
      </GlassmorphismCard>
    </section>
  );
}
