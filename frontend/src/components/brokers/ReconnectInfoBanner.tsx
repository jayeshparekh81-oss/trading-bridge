"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { getStoredLang, type Language } from "@/lib/language-detector";

const DISMISSED_KEY = "tb_reconnect_banner_dismissed";

// ─── Multi-language banner copy ─────────────────────────────────────────

interface BannerCopy {
  title: string;
  intro: string;
  bullets: readonly string[];
  dismissLabel: string;
}

const BANNER: Record<Language, BannerCopy> = {
  hinglish: {
    title: "📌 Daily Reconnect Required (SEBI Compliance)",
    intro:
      "Indian brokers (Fyers, Dhan, Zerodha — sab) ko 24-hour re-authentication chahiye, security ke liye.",
    bullets: [
      "✅ Industry standard — Tradetron, AlgoTest, Streak sab same",
      "✅ TRADETRI deta hai 1-click reconnect (~10 seconds)",
    ],
    dismissLabel: "Dismiss banner",
  },
  en: {
    title: "📌 Daily Reconnect Required (SEBI Compliance)",
    intro:
      "Indian brokers (Fyers, Dhan, Zerodha — all of them) require 24-hour re-authentication for security.",
    bullets: [
      "✅ Industry standard — same on Tradetron, AlgoTest, Streak",
      "✅ TRADETRI provides 1-click reconnect (~10 seconds)",
    ],
    dismissLabel: "Dismiss banner",
  },
  // REVIEW: Hindi rendering — native check before launch announcement
  hi: {
    title: "📌 Daily Reconnect ज़रूरी है (SEBI Compliance)",
    intro:
      "Indian brokers (Fyers, Dhan, Zerodha — सब) को 24-hour re-authentication चाहिए, security के लिए।",
    bullets: [
      "✅ Industry standard — Tradetron, AlgoTest, Streak सब same",
      "✅ TRADETRI देता है 1-click reconnect (~10 seconds)",
    ],
    dismissLabel: "Banner dismiss",
  },
  // REVIEW: Gujarati rendering — native check before launch announcement
  gu: {
    title: "📌 Daily Reconnect જરૂરી છે (SEBI Compliance)",
    intro:
      "Indian brokers (Fyers, Dhan, Zerodha — બધા) ને 24-hour re-authentication જોઈએ, security માટે.",
    bullets: [
      "✅ Industry standard — Tradetron, AlgoTest, Streak બધા same",
      "✅ TRADETRI આપે છે 1-click reconnect (~10 seconds)",
    ],
    dismissLabel: "Banner dismiss",
  },
};

// ─── Component ──────────────────────────────────────────────────────────

export function ReconnectInfoBanner() {
  const [dismissed, setDismissed] = useState(false);
  const [lang, setLang] = useState<Language>("hinglish");

  // Hydrate dismissal + language from localStorage on mount.
  // Server returns the default ("hinglish", undismissed) so SSR
  // matches; the client then restores any stored values.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const isDismissed = localStorage.getItem(DISMISSED_KEY) === "1";
    const storedLang = getStoredLang();
    /* eslint-disable react-hooks/set-state-in-effect -- one-shot mount restore from localStorage */
    if (isDismissed) setDismissed(true);
    if (storedLang !== "hinglish") setLang(storedLang);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  function handleDismiss() {
    setDismissed(true);
    if (typeof window !== "undefined") {
      localStorage.setItem(DISMISSED_KEY, "1");
    }
  }

  if (dismissed) return null;
  const copy = BANNER[lang];

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.25 }}
      >
        <GlassmorphismCard hover={false} className="relative border-accent-blue/30">
          <button
            type="button"
            onClick={handleDismiss}
            aria-label={copy.dismissLabel}
            className="absolute top-2 right-2 rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>

          <div className="flex items-center gap-2 mb-2 pr-8">
            <h2 className="text-base md:text-lg font-semibold leading-tight">
              {copy.title}
            </h2>
          </div>
          <p className="text-sm text-muted-foreground mb-3">{copy.intro}</p>
          <ul className="space-y-1 text-sm">
            {copy.bullets.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </GlassmorphismCard>
      </motion.div>
    </AnimatePresence>
  );
}
