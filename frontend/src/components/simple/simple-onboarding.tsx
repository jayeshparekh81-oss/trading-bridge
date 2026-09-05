"use client";

/**
 * Simple onboarding (C6) — three steps for a NEW signup: bhasha → broker →
 * strategy. Nothing here can trap the customer: every step has "Baad mein".
 * Finishing (or skipping) POSTs /onboarding/complete, then refreshes the auth
 * user BEFORE navigating — the first-login blink fix must hold on this path
 * too (the layout guard reads onboarding_step from the auth context).
 */

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { Landmark, Store, Languages, Loader2, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLanguage } from "@/contexts/LanguageContext";
import { useLadderOptional } from "@/hooks/useLadder";
import { t } from "@/lib/simple/copy";
import { SIMPLE_LANGS, ensureSimpleDefaultLanguage, mirrorLanguage } from "@/lib/simple/language-sync";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";

type Step = 1 | 2 | 3;

export function SimpleOnboarding() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const { lang, setLang } = useLanguage();
  const ladder = useLadderOptional();
  const reduce = useReducedMotion();
  const [step, setStep] = useState<Step>(1);
  const [busy, setBusy] = useState(false);
  // Step 1 starts on Hinglish unless the customer already chose a language.
  useEffect(() => ensureSimpleDefaultLanguage(setLang), [setLang]);

  /** Complete on the server, refresh the auth user, THEN go. */
  async function finish(href: string) {
    setBusy(true);
    try {
      await api.post("/onboarding/complete", {});
    } catch (err) {
      // Never trap the customer; the server reconciles on the next /me.
      const msg = err instanceof ApiError ? err.detail : null;
      if (msg && typeof msg === "string") toast.error(msg);
    }
    ladder?.markSimpleOnboardingDone();
    await refreshUser();
    router.push(href);
  }

  const L = (k: Parameters<typeof t>[1]) => t(lang, k);
  const titleKey = step === 1 ? "ob_step_lang" : step === 2 ? "ob_step_broker" : "ob_step_strategy";
  const bodyKey = step === 1 ? "ob_step_lang_body" : step === 2 ? "ob_step_broker_body" : "ob_step_strategy_body";
  const Icon = step === 1 ? Languages : step === 2 ? Landmark : Store;

  return (
    <div className="min-h-screen px-4 py-8 md:py-12 flex flex-col" data-testid="simple-onboarding" data-step={step}>
      <div className="mx-auto w-full max-w-md flex items-center justify-between">
        <Logo width={36} height={36} variant="icon" />
        <div className="flex items-center gap-1.5" aria-label={`step ${step} of 3`}>
          {[1, 2, 3].map((n) => (
            <span key={n} aria-hidden="true" className={cn("h-1.5 rounded-full transition-all", n <= step ? "w-6 bg-profit" : "w-2 bg-white/15")} />
          ))}
        </div>
      </div>

      <div className="mx-auto w-full max-w-md flex-1 flex flex-col justify-center">
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={reduce ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? undefined : { opacity: 0, y: -12 }}
            transition={{ duration: 0.25 }}
            className="glass rounded-3xl border border-white/10 p-6 md:p-8"
          >
            <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-profit/10 ring-1 ring-profit/25">
              <Icon className="h-7 w-7 text-profit" aria-hidden="true" />
            </span>
            <h1 className="mt-4 text-2xl md:text-3xl font-extrabold text-foreground">{L(titleKey)}</h1>
            <p className="mt-2 text-sm md:text-base text-foreground/80">{L(bodyKey)}</p>
            {step === 3 && (
              <p className="mt-3 text-sm md:text-base text-profit/90 font-medium" data-testid="ob-levels-note">
                {L("ob_levels_note")}
              </p>
            )}

            {step === 1 && (
              <div className="mt-5 grid grid-cols-2 gap-2" data-testid="ob-lang-grid">
                {SIMPLE_LANGS.map((l) => (
                  <button
                    key={l.code}
                    type="button"
                    data-testid={`ob-lang-${l.code}`}
                    onClick={() => {
                      setLang(l.code);
                      mirrorLanguage(l.code);
                    }}
                    className={cn(
                      "rounded-2xl border px-3 py-3 text-base font-semibold transition-colors",
                      lang === l.code ? "border-profit bg-profit/10 text-foreground" : "border-white/10 text-foreground/80 hover:border-profit/40",
                    )}
                  >
                    {l.native}
                  </button>
                ))}
              </div>
            )}

            <div className="mt-6 flex flex-col gap-2">
              {step === 1 && (
                <button
                  type="button"
                  data-testid="ob-next"
                  onClick={() => setStep(2)}
                  className="inline-flex items-center justify-center gap-1 rounded-full bg-profit px-5 py-3 text-base font-bold text-[#0A0E1A]"
                >
                  {L("ob_next")} <ChevronRight className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
              {step === 2 && (
                <>
                  <button
                    type="button"
                    data-testid="ob-go-broker"
                    disabled={busy}
                    onClick={() => finish("/brokers")}
                    className="inline-flex items-center justify-center gap-1 rounded-full bg-profit px-5 py-3 text-base font-bold text-[#0A0E1A]"
                  >
                    {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : L("tile_broker")}
                  </button>
                  <button type="button" data-testid="ob-next" onClick={() => setStep(3)} className="inline-flex items-center justify-center rounded-full border border-white/15 px-5 py-3 text-base font-semibold text-foreground">
                    {L("ob_skip")}
                  </button>
                </>
              )}
              {step === 3 && (
                <>
                  <button
                    type="button"
                    data-testid="ob-go-strategy"
                    disabled={busy}
                    onClick={() => finish("/marketplace")}
                    className="inline-flex items-center justify-center gap-1 rounded-full bg-profit px-5 py-3 text-base font-bold text-[#0A0E1A]"
                  >
                    {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : L("tile_strategy")}
                  </button>
                  <button
                    type="button"
                    data-testid="ob-done"
                    disabled={busy}
                    onClick={() => finish("/")}
                    className="inline-flex items-center justify-center rounded-full border border-white/15 px-5 py-3 text-base font-semibold text-foreground"
                  >
                    {L("ob_done")}
                  </button>
                </>
              )}
            </div>
          </motion.div>
        </AnimatePresence>
        {step < 3 && (
          <button
            type="button"
            data-testid="ob-skip-all"
            disabled={busy}
            onClick={() => finish("/")}
            className="mt-4 self-center text-sm text-muted-foreground hover:text-foreground"
          >
            {L("ob_later")}
          </button>
        )}
      </div>
    </div>
  );
}
