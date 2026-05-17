/**
 * WelcomeModal — first-login welcome screen, dismissable.
 *
 * Two CTAs: start the tour (primary) or postpone with "Later".
 * Language toggle is shared with the rest of the tour via the
 * useOnboarding hook.
 */

"use client";

import { motion } from "framer-motion";
import { Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Lang } from "@/lib/onboarding/tourSteps";
import { WELCOME_COPY } from "@/lib/onboarding/tourSteps";

export interface WelcomeModalProps {
  userName: string;
  lang: Lang;
  onLangChange: (next: Lang) => void;
  onStart: () => void;
  onLater: () => void;
}

export function WelcomeModal({
  userName,
  lang,
  onLangChange,
  onStart,
  onLater,
}: WelcomeModalProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-welcome-title"
      data-testid="onboarding-welcome-modal"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 supports-backdrop-filter:backdrop-blur-sm p-4"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="relative w-full max-w-md rounded-2xl border border-white/10 bg-neutral-900/80 supports-backdrop-filter:backdrop-blur-xl p-6 shadow-2xl shadow-black/60"
      >
        {/* Top row: language toggle + close (Later) */}
        <div className="mb-4 flex items-center justify-between">
          <LangToggle lang={lang} onChange={onLangChange} />
          <button
            type="button"
            aria-label={lang === "hi" ? "Band karo" : "Close"}
            onClick={onLater}
            data-testid="onboarding-welcome-close"
            className="rounded-md p-1 text-neutral-400 hover:bg-white/5 hover:text-neutral-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <h2
          id="onboarding-welcome-title"
          data-testid="onboarding-welcome-title"
          className="mb-3 text-xl font-bold text-neutral-100"
        >
          {WELCOME_COPY.greeting[lang](userName)}
        </h2>

        <p
          data-testid="onboarding-welcome-tagline"
          className="mb-5 text-sm leading-relaxed text-neutral-300"
        >
          {WELCOME_COPY.tagline[lang]}
        </p>

        <div className="mb-6 inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
          <Sparkles className="h-3 w-3" aria-hidden="true" />
          <span data-testid="onboarding-welcome-badge">
            {WELCOME_COPY.trustBadge[lang]}
          </span>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <Button
            type="button"
            onClick={onStart}
            data-testid="onboarding-welcome-start"
            className="flex-1 bg-emerald-500 text-emerald-950 hover:bg-emerald-400"
          >
            {WELCOME_COPY.startCta[lang]}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={onLater}
            data-testid="onboarding-welcome-later"
            className="flex-1 text-neutral-300 hover:bg-white/5"
          >
            {WELCOME_COPY.laterCta[lang]}
          </Button>
        </div>
      </motion.div>
    </div>
  );
}

function LangToggle({
  lang,
  onChange,
}: {
  lang: Lang;
  onChange: (next: Lang) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Language"
      data-testid="onboarding-lang-toggle"
      className="inline-flex rounded-md border border-white/10 bg-black/30 p-0.5 text-xs"
    >
      <button
        type="button"
        onClick={() => onChange("en")}
        data-testid="onboarding-lang-en"
        aria-pressed={lang === "en"}
        className={`rounded-sm px-2 py-1 transition-colors ${
          lang === "en"
            ? "bg-white/10 text-white"
            : "text-neutral-400 hover:text-neutral-200"
        }`}
      >
        English
      </button>
      <button
        type="button"
        onClick={() => onChange("hi")}
        data-testid="onboarding-lang-hi"
        aria-pressed={lang === "hi"}
        className={`rounded-sm px-2 py-1 transition-colors ${
          lang === "hi"
            ? "bg-white/10 text-white"
            : "text-neutral-400 hover:text-neutral-200"
        }`}
      >
        हिंदी
      </button>
    </div>
  );
}
