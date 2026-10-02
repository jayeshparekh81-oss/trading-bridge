"use client";

import { useState, Suspense } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { Input } from "@/shared/ui/input";
import { GlowButton } from "@/shared/ui/glow-button";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { DEFAULT_NEXT, withNext } from "@/lib/safe-next";
import { ReturnPathProbe } from "@/components/auth/return-path-probe";
import { useSignupOpen } from "@/hooks/useSignupOpen";
import { signupClosedLine } from "@/lib/signup-status";
import { authCopy } from "@/lib/i18n/copy/auth";
import { useCopy } from "@/lib/i18n/core";
import { Logo } from "@/components/logo";
import { MantrasModal } from "@/components/mantras-modal";
import { HighlightTri } from "@/components/brand/highlight-tri";
import { ConvictionPanel } from "@/components/brand/conviction-panel";

function LoginPageInner() {
  // ?next= — where the customer was headed before we asked them to log in.
  // Sanitised at the point of USE (auth.tsx) as well as in the probe; a bad value
  // silently degrades to "/" rather than blocking the login. The ONLY useSearchParams()
  // call lives in <ReturnPathProbe> so this page renders on the SERVER (2 Oct 2026:
  // the whole page used to bail out to a blank client render — see the probe's header).
  const [nextPath, setNextPath] = useState<string>(DEFAULT_NEXT);
  const { login } = useAuth();
  const signup = useSignupOpen();
  const { c, lang } = useCopy(authCopy);
  const [showPassword, setShowPassword] = useState(false);
  const [mantrasOpen, setMantrasOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password, nextPath);
    } catch {
      // toast already shown by auth context
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center bg-background px-4 py-10">
      {/* The only client-side bailout on this page: the ?next= reader, which renders nothing. */}
      <Suspense fallback={null}>
        <ReturnPathProbe onPath={setNextPath} />
      </Suspense>
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-accent-blue/5 via-transparent to-accent-purple/5" />

      {/* Hypnotic full-page Kalachakra mandala — PRESERVED */}
      <div className="fixed inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
        <img
          src="/tradetri-hero.png"
          alt=""
          aria-hidden="true"
          className="max-h-[95vh] w-auto h-auto max-w-[95vw] opacity-[0.22] select-none"
          style={{ animation: "none", pointerEvents: "none" }}
        />
      </div>
      {/* Darkening vignette — deepens edges, spotlights center — PRESERVED */}
      <div className="fixed inset-0 pointer-events-none bg-gradient-radial from-transparent via-black/30 to-black/70" style={{ background: "var(--gradient-vignette)" }} />

      {/* Two-column hero — left = brand + proof, right = login card; stacks on mobile */}
      <div className="relative w-full max-w-6xl grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-14 items-center">

        {/* LEFT — brand + honest proof */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="space-y-6 text-center lg:text-left"
        >
          {/* Logo — PRESERVED (icon + wordmark) */}
          <motion.div
            className="flex items-center justify-center lg:justify-start gap-2"
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.15, ease: "easeOut" }}
          >
            <Logo variant="icon" width={56} height={56} priority />
            <Logo variant="wordmark" height={54} />
          </motion.div>

          {/* PAST · PRESENT · FUTURE tricolor — PRESERVED */}
          <motion.div
            className="mx-auto lg:mx-0 grid grid-cols-3 items-center font-mono text-xs tracking-[0.1em] font-bold"
            style={{ width: "min(100%, 260px)" }}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            <span className="text-left text-flag-saffron">PAST</span>
            <span className="text-center text-white">PRESENT</span>
            <span className="text-right text-flag-green">FUTURE</span>
          </motion.div>

          {/* Eyebrow + honest H1 + honest subline */}
          <motion.div
            className="space-y-3"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            <p className="text-xs font-mono tracking-[0.25em] text-accent-gold/70 uppercase">
              {c.eyebrow}
            </p>
            <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-[1.05]">
              {c.h1_a}<br />
              <span className="bg-gradient-to-b from-brand-gold to-brand-green bg-clip-text text-transparent">
                {c.h1_b}
              </span>
            </h2>
            <p className="text-13 sm:text-sm text-foreground/85 leading-relaxed max-w-md mx-auto lg:mx-0">
              {c.sub}
            </p>
            <p className="text-xs text-muted-foreground font-mono tracking-[0.1em]">
              {c.facts}
            </p>
          </motion.div>

          {/* AI conviction proof panel (illustrative / EXAMPLE) */}
          <motion.div
            className="max-w-md mx-auto lg:mx-0"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
          >
            <ConvictionPanel />
          </motion.div>

          {/* Track Record CTA → /showcase */}
          <motion.div
            className="space-y-1"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
          >
            <Link
              href="/showcase"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-accent-blue hover:underline"
            >
              {c.track_record}
            </Link>
            <p className="text-xs text-muted-foreground/60 leading-relaxed max-w-md mx-auto lg:mx-0">
              {c.track_record_sub}
            </p>
          </motion.div>

          {/* Sanskrit cultural signature — PRESERVED (opens MantrasModal) */}
          <motion.button
            type="button"
            onClick={() => setMantrasOpen(true)}
            className="space-y-1 group cursor-pointer mx-auto lg:mx-0 block"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.7 }}
            aria-label={c.mantras_aria}
          >
            <p
              lang="hi"
              className="text-13 tracking-[0.18em] text-accent-gold/60 group-hover:text-accent-gold/80 font-serif transition-colors"
            >
              ॐ · <HighlightTri prefix="त्रि" rest="काल" /> ·{" "}
              <HighlightTri prefix="त्रि" rest="शूल" /> ·{" "}
              <HighlightTri prefix="त्रि" rest="स्केलियन" /> · कालचक्र
            </p>
            <p className="text-xs tracking-[0.25em] text-muted-foreground/70 group-hover:text-muted-foreground font-mono transition-colors">
              <HighlightTri prefix="TRI" rest="KALA" /> ·{" "}
              <HighlightTri prefix="TRI" rest="SHUL" /> ·{" "}
              <HighlightTri prefix="TRI" rest="SKELION" /> · KALACHAKRA
            </p>
            <p className="text-xs tracking-[0.3em] text-accent-gold/50 group-hover:text-accent-gold/90 font-mono pt-1 uppercase transition-colors">
              {c.tap_decode}
            </p>
          </motion.button>

          {/* Honest, substantiable badges */}
          <motion.div
            className="flex items-center justify-center lg:justify-start gap-2 flex-wrap"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.8 }}
          >
            <span className="text-xs tracking-widest px-2 py-1 rounded-full border border-white/30 text-white/90 bg-white/5">
              {c.badge_signal_first}
            </span>
            <span className="text-xs tracking-widest px-2 py-1 rounded-full border border-flag-saffron/50 text-flag-saffron bg-flag-saffron/10">
              {c.badge_your_broker}
            </span>
            <span className="text-xs tracking-widest px-2 py-1 rounded-full border border-profit/40 text-profit bg-profit/10">
              {c.badge_sebi}
            </span>
            <span className="text-xs tracking-widest px-2 py-1 rounded-full border border-accent-blue/40 text-accent-blue bg-accent-blue/10">
              {c.badge_encrypted}
            </span>
          </motion.div>
        </motion.div>

        {/* RIGHT — login card */}
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="w-full max-w-md mx-auto lg:ml-auto order-first lg:order-none"
        >
          <div className="glass p-7 sm:p-8 space-y-6 relative rounded-3xl">
            <div className="text-center space-y-1">
              <h1 className="text-lg font-semibold text-foreground">{c.login_title}</h1>
              <p className="text-sm text-muted-foreground">{c.login_sub}</p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground/80">
                  {c.email}
                </label>
                <Input
                  type="email"
                  placeholder={c.email_placeholder}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="bg-muted/50 border-border h-11"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground/80">
                  {c.password}
                </label>
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder={c.password_placeholder}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="bg-muted/50 border-border h-11 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-1 top-1/2 -translate-y-1/2 inline-flex h-11 w-11 items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
                    aria-label={showPassword ? c.hide_password : c.show_password}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              <GlowButton className="w-full" size="lg" type="submit" disabled={loading || !email || !password}>
                {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : c.login_cta}
              </GlowButton>
            </form>

            {/* Links */}
            <div className="text-center space-y-2 text-sm">
              {signup === "open" ? (
                <p className="text-muted-foreground">
                  {c.new_here}{" "}
                  <Link
                    href={withNext("/register", nextPath)}
                    className="inline-flex min-h-11 items-center text-accent-blue hover:underline font-medium"
                  >
                    {c.create_account_free}
                  </Link>
                </p>
              ) : (
                <p className="text-muted-foreground" data-testid="login-signup-closed">{signupClosedLine(lang)}</p>
              )}
            </div>
          </div>
        </motion.div>
      </div>

      {/* Footer — honest risk disclaimer + Vadodara line */}
      <footer className="relative w-full max-w-3xl mt-10 space-y-3">
        <p className="text-xs leading-relaxed text-muted-foreground/55 text-center">
          {c.footer_risk}
        </p>
        <p className="text-center text-xs text-muted-foreground/60 tracking-wider">
          {c.footer_built}
        </p>
      </footer>

      <MantrasModal open={mantrasOpen} onClose={() => setMantrasOpen(false)} />
    </div>
  );
}

/**
 * 2 Oct 2026: this page is rendered on the SERVER again. It used to be wrapped whole in
 * `<Suspense fallback={null}>` because `useSearchParams()` forces a client-side bailout — and
 * that made the served HTML of /login an EMPTY shell (measured on build 67a3e41e: only the footer
 * disclaimer; a phone saw a blank screen until ~285 KB gzip of JS arrived). The one
 * `useSearchParams()` call now lives in <ReturnPathProbe>, inside its own Suspense, so the
 * title, the form and the way back are in the first byte of HTML.
 */
export default function LoginPage() {
  return <LoginPageInner />;
}
