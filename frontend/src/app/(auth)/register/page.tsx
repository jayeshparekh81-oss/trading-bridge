"use client";

import { useState, useMemo, Suspense } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff, Check, X, Loader2 } from "lucide-react";
import { Input } from "@/shared/ui/input";
import { GlowButton } from "@/shared/ui/glow-button";
import { Progress } from "@/shared/ui/progress";
import { cn } from "@/shared/lib/utils";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { DEFAULT_NEXT, withNext } from "@/lib/safe-next";
import { ReturnPathProbe } from "@/components/auth/return-path-probe";
import { Logo } from "@/components/logo";
import { MantrasModal } from "@/components/mantras-modal";
import { HighlightTri } from "@/components/brand/highlight-tri";
import { RiskAcknowledgment } from "@/components/compliance/RiskAcknowledgment";
import { PASSWORD_RULES } from "@/lib/auth-errors";
import { useSignupOpen } from "@/hooks/useSignupOpen";
import { SIGNUP_INVITE_ONLY_LINE } from "@/lib/signup-status";

function getPasswordStrength(pw: string): {
  score: number;
  label: string;
  color: string;
} {
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[a-z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;

  if (score <= 1) return { score: 20, label: "Kamzor", color: "text-loss" };
  if (score <= 2) return { score: 40, label: "Theek-thaak", color: "text-accent-gold" };
  if (score <= 3) return { score: 60, label: "Achha", color: "text-accent-blue" };
  if (score <= 4) return { score: 80, label: "Mazboot", color: "text-profit" };
  return { score: 100, label: "Bahut mazboot", color: "text-profit" };
}

function RegisterPageInner() {
  // ?next= — carried from wherever the customer clicked Subscribe, so they
  // land back on that strategy instead of a generic dashboard. The ONLY useSearchParams()
  // call lives in <ReturnPathProbe> so this page renders on the SERVER (2 Oct 2026).
  const [nextPath, setNextPath] = useState<string>(DEFAULT_NEXT);
  const { register } = useAuth();
  const signup = useSignupOpen();
  const [showPassword, setShowPassword] = useState(false);
  const [mantrasOpen, setMantrasOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: "",
  });
  // SEBI-aware risk acknowledgment — required before account create.
  // ``showRiskError`` only flips after a submit attempt; we don't
  // shout at users while they're still filling the form.
  const [riskAck, setRiskAck] = useState(false);
  const [showRiskError, setShowRiskError] = useState(false);

  const strength = useMemo(
    () => getPasswordStrength(form.password),
    [form.password]
  );

  const passwordsMatch =
    form.password.length > 0 && form.password === form.confirmPassword;
  const rulesOk = PASSWORD_RULES.every((r) => r.test(form.password));
  // What is still missing, in plain words — a disabled button must say why (rule 8).
  const missing = [
    !form.full_name && "naam",
    !form.email && "email",
    !rulesOk && "password ki saari line hari (✓)",
    !!form.password && !passwordsMatch && "dono password same",
    !riskAck && "risk wala tick",
  ].filter(Boolean) as string[];

  const update = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-8">
      {/* The only client-side bailout on this page: the ?next= reader, which renders nothing. */}
      <Suspense fallback={null}>
        <ReturnPathProbe onPath={setNextPath} />
      </Suspense>
      <div className="absolute inset-0 bg-gradient-to-br from-accent-purple/5 via-transparent to-accent-blue/5" />

      {/* Hypnotic full-page Kalachakra mandala */}
      <div className="fixed inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
        <img
          src="/tradetri-hero.png"
          alt=""
          aria-hidden="true"
          className="max-h-[95vh] w-auto h-auto max-w-[95vw] opacity-[0.22] select-none"
          style={{ animation: "none", pointerEvents: "none" }}
        />
      </div>
      {/* Darkening vignette — deepens edges, spotlights center */}
      <div className="fixed inset-0 pointer-events-none bg-gradient-radial from-transparent via-black/30 to-black/70" style={{ background: "var(--gradient-vignette)" }} />

      <motion.div
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6 }}
        className="relative w-full max-w-md"
      >
        <div className="p-8 space-y-6 relative backdrop-blur-xs rounded-3xl">
          {/* Amber glow aura */}
          

          {/* Logo */}
          <div className="text-center space-y-3 relative">
            <motion.div
              className="flex items-center justify-center gap-2"
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.7, delay: 0.15, ease: "easeOut" }}
            >
              <Logo variant="icon" width={56} height={56} priority />
              <Logo variant="wordmark" height={54} />
            </motion.div>

            <motion.div
              className="mx-auto grid grid-cols-3 items-center font-mono text-xs tracking-[0.1em] font-bold -mt-2"
              style={{ width: "min(100%, 260px)" }}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
            >
              <span className="text-left text-flag-saffron">PAST</span>
              <span className="text-center text-white">PRESENT</span>
              <span className="text-right text-flag-green">FUTURE</span>
            </motion.div>

            <motion.div
              className="space-y-1"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
            >
              <p className="text-13 text-foreground/90 font-medium tracking-wide">
                Pehle nakli paise se chalao, dekho, samjho. Phir faisla aapka.
              </p>
              <p className="text-xs text-muted-foreground font-mono tracking-[0.1em]">
                20 saal ka NSE data · Dhan aur Fyers se seedha jude · server Mumbai me
              </p>
            </motion.div>

            <motion.button
              type="button"
              onClick={() => setMantrasOpen(true)}
              className="pt-1 space-y-1 group cursor-pointer mx-auto block"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.6 }}
              aria-label="Learn what these mantras mean"
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
                ✨ Tap to decode
              </p>
            </motion.button>

            <motion.div
              className="flex items-center justify-center gap-2 pt-2 flex-wrap"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.75 }}
            >
              <span className="text-xs tracking-widest px-2 py-1 rounded-full border border-accent-purple/40 text-accent-purple bg-accent-purple/10">
                PAPER FIRST
              </span>
              <span className="text-xs tracking-widest px-2 py-1 rounded-full border border-flag-saffron/50 text-flag-saffron bg-flag-saffron/10">
                ENCRYPTED
              </span>
              <span className="text-xs tracking-widest px-2 py-1 rounded-full border border-white/30 text-white/90 bg-white/5">
                AAPKA BROKER · AAPKE FUNDS
              </span>
              <span className="text-xs tracking-widest px-2 py-1 rounded-full border border-profit/40 text-profit bg-profit/10">
                SEBI AWARE
              </span>
            </motion.div>
          </div>

          {/* Form — the ONE thing this screen is for, said in its title (5-second test). */}
          <div className="space-y-4">
            <div className="text-center space-y-1">
              <h1 className="text-xl font-bold text-foreground">Naya account banao</h1>
              <p className="text-sm text-muted-foreground">Free hai, card nahi chahiye. 2 minute lagenge.</p>
            </div>
            {signup !== "open" && (
              <p role="status" data-testid="register-invite-only" className="rounded-md border border-accent-gold/40 bg-accent-gold/10 p-3 text-sm text-foreground">
                {SIGNUP_INVITE_ONLY_LINE}
              </p>
            )}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground/80">
                Poora naam
              </label>
              <Input
                placeholder="Jayesh Parekh"
                value={form.full_name}
                onChange={(e) => update("full_name", e.target.value)}
                className="bg-muted/50 border-border h-11"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground/80">
                Email
              </label>
              <Input
                type="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                className="bg-muted/50 border-border h-11"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground/80">
                Phone (zaroori nahi)
              </label>
              <Input
                type="tel"
                placeholder="+91 98765 43210"
                value={form.phone}
                onChange={(e) => update("phone", e.target.value)}
                className="bg-muted/50 border-border h-11"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground/80">
                Password
              </label>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="Naya password"
                  value={form.password}
                  onChange={(e) => update("password", e.target.value)}
                  className="bg-muted/50 border-border h-11 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-1 top-1/2 -translate-y-1/2 inline-flex h-11 w-11 items-center justify-center text-muted-foreground hover:text-foreground"
                  aria-label="Password dikhao ya chhupao"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {/* The server's own password rules, shown BEFORE the customer submits — so the
                  first "no" never comes as an English error after tapping the button. */}
              <ul className="mt-2 grid grid-cols-1 gap-1 text-sm sm:grid-cols-2" data-testid="password-rules">
                {PASSWORD_RULES.map((r) => {
                  const ok = r.test(form.password);
                  return (
                    <li key={r.key} data-ok={ok ? "yes" : "no"} className={cn("flex items-center gap-1.5", ok ? "text-profit" : "text-muted-foreground")}>
                      {ok ? <Check className="h-4 w-4" aria-hidden /> : <X className="h-4 w-4 opacity-60" aria-hidden />}
                      {r.label}
                    </li>
                  );
                })}
              </ul>
              {form.password.length > 0 && (
                <div className="space-y-1.5 mt-2">
                  <Progress value={strength.score} className="h-1.5" />
                  <p className={cn("text-sm font-medium", strength.color)}>
                    {strength.label}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground/80">
                Password dobara likho
              </label>
              <div className="relative">
                <Input
                  type="password"
                  placeholder="Wahi password dobara"
                  value={form.confirmPassword}
                  onChange={(e) => update("confirmPassword", e.target.value)}
                  className="bg-muted/50 border-border h-11 pr-10"
                />
                {form.confirmPassword.length > 0 && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2">
                    {passwordsMatch ? (
                      <Check className="h-4 w-4 text-profit" />
                    ) : (
                      <X className="h-4 w-4 text-loss" />
                    )}
                  </span>
                )}
              </div>
            </div>

            <RiskAcknowledgment
              checked={riskAck}
              onChange={(next) => {
                setRiskAck(next);
                if (next) setShowRiskError(false);
              }}
              showError={showRiskError}
              lang="hi"
            />

            <GlowButton
              className="w-full"
              size="lg"
              variant="profit"
              disabled={loading || !form.email || !form.full_name || !rulesOk || !passwordsMatch || !riskAck}
              onClick={async () => {
                if (!riskAck) {
                  setShowRiskError(true);
                  return;
                }
                setLoading(true);
                try {
                  await register({
                    email: form.email,
                    password: form.password,
                    full_name: form.full_name,
                    phone: form.phone || undefined,
                  }, nextPath);
                } catch { /* toast shown by auth context */ }
                finally { setLoading(false); }
              }}
            >
              {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : "Account banao (free)"}
            </GlowButton>
            {missing.length > 0 && !loading ? (
              <p className="text-center text-sm text-muted-foreground" data-testid="register-missing">
                Button tab chalega jab yeh ho jaaye: {missing.join(", ")}.
              </p>
            ) : null}
          </div>

          <div className="text-center text-sm">
            <p className="text-muted-foreground">
              Pehle se account hai?{" "}
              <Link
                href={withNext("/login", nextPath)}
                className="inline-flex min-h-11 items-center text-accent-blue hover:underline font-medium"
              >
                Login karo
              </Link>
            </p>
          </div>
        </div>

        <MantrasModal open={mantrasOpen} onClose={() => setMantrasOpen(false)} />

        <p className="text-center text-xs text-muted-foreground/60 mt-6 tracking-wider">
          ENCRYPTED · BUILT IN VADODARA 🇮🇳
        </p>
      </motion.div>
    </div>
  );
}

/**
 * 2 Oct 2026: rendered on the SERVER again — the page-wide `<Suspense fallback={null}>` that
 * `useSearchParams()` used to force made the served HTML of /register an EMPTY shell (measured
 * on build 67a3e41e). The one `useSearchParams()` call now lives in <ReturnPathProbe>.
 */
export default function RegisterPage() {
  return <RegisterPageInner />;
}
