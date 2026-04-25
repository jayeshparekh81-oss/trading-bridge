"use client";

import { useEffect, useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Sparkles, Send } from "lucide-react";
import { toast } from "sonner";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Input } from "@/components/ui/input";
import { GlowButton } from "@/components/ui/glow-button";
import { getStoredLang, type Language } from "@/lib/language-detector";
import { FOUNDER_WHATSAPP_NUMBER } from "@/lib/algomitra-personality";
import { cn } from "@/lib/utils";

const DISMISSED_KEY = "tb_reconnect_banner_dismissed";
const SAVED_EMAIL_KEY = "tb_waitlist_email";
const VALID_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// ─── Multi-language banner copy ─────────────────────────────────────────

interface BannerCopy {
  title: string;
  intro: string;
  bullets: readonly string[];
  phase2Heading: string;
  phase2Bullets: readonly string[];
  premiumHeading: string;
  premiumLead: string;
  premiumBullets: readonly string[];
  disclaimer: string;
  waitlistHeading: string;
  emailPlaceholder: string;
  joinButton: string;
  successToast: string;
  invalidEmail: string;
  whatsappTemplate: (email: string) => string;
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
    phase2Heading: "🚀 Phase 2 (target: 4-6 weeks)",
    phase2Bullets: [
      "Smart auto-refresh (~90% seamless, estimated)",
      "Email + WhatsApp reminders",
      "AlgoMitra notifications",
    ],
    premiumHeading: "🏆 Premium Tier (target: 3-6 months)",
    premiumLead: "ZERO RECONNECT via official broker partnerships",
    premiumBullets: [
      "Master account routing",
      "Setup once, trade for months",
      "White-glove onboarding",
      "Priority support",
    ],
    disclaimer: "Targets, not promises — honest expectations.",
    waitlistHeading: "Premium launch hone par notify chahiye?",
    emailPlaceholder: "tumhari email",
    joinButton: "Join Premium Waitlist",
    successToast:
      "Founder ko WhatsApp message bhej diya — wo personally reply karenge.",
    invalidEmail: "Bhai, valid email enter kar.",
    whatsappTemplate: (email) =>
      `Hi Jayesh bhai, Premium Tier waitlist join karna hai.\nEmail: ${email}`,
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
    phase2Heading: "🚀 Phase 2 (target: 4-6 weeks)",
    phase2Bullets: [
      "Smart auto-refresh (~90% seamless, estimated)",
      "Email + WhatsApp reminders",
      "AlgoMitra notifications",
    ],
    premiumHeading: "🏆 Premium Tier (target: 3-6 months)",
    premiumLead: "ZERO RECONNECT via official broker partnerships",
    premiumBullets: [
      "Master account routing",
      "Setup once, trade for months",
      "White-glove onboarding",
      "Priority support",
    ],
    disclaimer: "Targets, not promises — honest expectations.",
    waitlistHeading: "Want a heads-up when Premium launches?",
    emailPlaceholder: "your email",
    joinButton: "Join Premium Waitlist",
    successToast:
      "Sent the founder a WhatsApp message — he'll reply personally.",
    invalidEmail: "Please enter a valid email.",
    whatsappTemplate: (email) =>
      `Hi Jayesh ji, I want to join the Premium Tier waitlist.\nMy email: ${email}\nNotify me when zero-reconnect launches!`,
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
    phase2Heading: "🚀 Phase 2 (target: 4-6 हफ्ते)",
    phase2Bullets: [
      "Smart auto-refresh (~90% seamless, estimated)",
      "Email + WhatsApp reminders",
      "AlgoMitra notifications",
    ],
    premiumHeading: "🏆 Premium Tier (target: 3-6 महीने)",
    premiumLead: "ZERO RECONNECT — official broker partnerships के through",
    premiumBullets: [
      "Master account routing",
      "Setup एक बार, trade कई महीने",
      "White-glove onboarding",
      "Priority support",
    ],
    disclaimer: "Targets हैं, promises नहीं — honest expectations।",
    waitlistHeading: "Premium launch हो तो notify करूँ?",
    emailPlaceholder: "अपनी email डालो",
    joinButton: "Premium Waitlist में जुड़ो",
    successToast:
      "Founder को WhatsApp message भेज दिया — वो personally reply करेंगे।",
    invalidEmail: "भाई, valid email enter करो।",
    whatsappTemplate: (email) =>
      `नमस्ते Jayesh ji, मुझे Premium Tier waitlist में जोड़ें।\nमेरी email: ${email}`,
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
    phase2Heading: "🚀 Phase 2 (target: 4-6 અઠવાડિયા)",
    phase2Bullets: [
      "Smart auto-refresh (~90% seamless, estimated)",
      "Email + WhatsApp reminders",
      "AlgoMitra notifications",
    ],
    premiumHeading: "🏆 Premium Tier (target: 3-6 મહિના)",
    premiumLead: "ZERO RECONNECT — official broker partnerships દ્વારા",
    premiumBullets: [
      "Master account routing",
      "Setup એક વાર, trade ઘણા મહિના",
      "White-glove onboarding",
      "Priority support",
    ],
    disclaimer: "Targets છે, promises નથી — honest expectations.",
    waitlistHeading: "Premium launch થાય ત્યારે notify કરું?",
    emailPlaceholder: "તમારી email",
    joinButton: "Premium Waitlist માં જોડાઓ",
    successToast:
      "Founder ને WhatsApp message મોકલી દીધો — એ personally reply કરશે.",
    invalidEmail: "ભાઈ, valid email enter કરો.",
    whatsappTemplate: (email) =>
      `Namaste Jayesh ji, mane Premium Tier waitlist ma jodo.\nMari email: ${email}`,
    dismissLabel: "Banner dismiss",
  },
};

// ─── Component ──────────────────────────────────────────────────────────

export function ReconnectInfoBanner() {
  const [dismissed, setDismissed] = useState(false);
  const [lang, setLang] = useState<Language>("hinglish");
  const [email, setEmail] = useState("");

  // Hydrate dismissal + language + saved email from localStorage on mount.
  // Server returns the default ("hinglish", undismissed, no email) so SSR
  // matches; the client then restores any stored values.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const isDismissed = localStorage.getItem(DISMISSED_KEY) === "1";
    const storedLang = getStoredLang();
    const savedEmail = localStorage.getItem(SAVED_EMAIL_KEY) ?? "";
    /* eslint-disable react-hooks/set-state-in-effect -- one-shot mount restore from localStorage */
    if (isDismissed) setDismissed(true);
    if (storedLang !== "hinglish") setLang(storedLang);
    if (savedEmail) setEmail(savedEmail);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  function handleDismiss() {
    setDismissed(true);
    if (typeof window !== "undefined") {
      localStorage.setItem(DISMISSED_KEY, "1");
    }
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = email.trim();
    const copy = BANNER[lang];
    if (!VALID_EMAIL.test(trimmed)) {
      toast.error(copy.invalidEmail);
      return;
    }
    if (typeof window !== "undefined") {
      localStorage.setItem(SAVED_EMAIL_KEY, trimmed);
    }
    const text = encodeURIComponent(copy.whatsappTemplate(trimmed));
    const url = `https://wa.me/${FOUNDER_WHATSAPP_NUMBER}?text=${text}`;
    window.open(url, "_blank", "noopener");
    toast.success(copy.successToast);
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
          <ul className="space-y-1 mb-4 text-sm">
            {copy.bullets.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <div className="rounded-xl border border-border/60 bg-background/40 p-3">
              <div className="text-sm font-semibold mb-1.5">
                {copy.phase2Heading}
              </div>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {copy.phase2Bullets.map((b) => (
                  <li key={b}>• {b}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-accent-gold/30 bg-accent-gold/5 p-3">
              <div className="text-sm font-semibold mb-1 flex items-center gap-1">
                <Sparkles className="h-3.5 w-3.5 text-accent-gold" />
                {copy.premiumHeading}
              </div>
              <div className="text-xs font-medium text-accent-gold mb-1">
                {copy.premiumLead}
              </div>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {copy.premiumBullets.map((b) => (
                  <li key={b}>• {b}</li>
                ))}
              </ul>
            </div>
          </div>

          <p className="text-[11px] text-muted-foreground italic mb-3">
            {copy.disclaimer}
          </p>

          <form
            onSubmit={handleSubmit}
            className="flex flex-col sm:flex-row items-stretch gap-2 border-t border-border/60 pt-3"
          >
            <div className="flex-1">
              <label
                htmlFor="reconnect-banner-waitlist-email"
                className="text-xs font-medium text-muted-foreground mb-1 block"
              >
                {copy.waitlistHeading}
              </label>
              <Input
                id="reconnect-banner-waitlist-email"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder={copy.emailPlaceholder}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={cn("text-sm")}
              />
            </div>
            <GlowButton
              type="submit"
              size="sm"
              className="sm:self-end whitespace-nowrap"
            >
              <Send className="h-3.5 w-3.5 mr-1.5" />
              {copy.joinButton}
            </GlowButton>
          </form>
        </GlassmorphismCard>
      </motion.div>
    </AnimatePresence>
  );
}
