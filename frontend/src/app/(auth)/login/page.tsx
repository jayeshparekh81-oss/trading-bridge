"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { GlowButton } from "@/components/ui/glow-button";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { Logo } from "@/components/logo";
import { MantrasModal } from "@/components/mantras-modal";
import { HighlightTri } from "@/components/brand/highlight-tri";
import { ConvictionPanel } from "@/components/brand/conviction-panel";

export default function LoginPage() {
  const { login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [mantrasOpen, setMantrasOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
    } catch {
      // toast already shown by auth context
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center bg-background px-4 py-10">
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
      <div className="fixed inset-0 pointer-events-none bg-gradient-radial from-transparent via-black/30 to-black/70" style={{ background: "radial-gradient(ellipse at center, transparent 20%, rgba(0,0,0,0.4) 60%, rgba(0,0,0,0.8) 100%)" }} />

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
            className="mx-auto lg:mx-0 grid grid-cols-3 items-center font-mono text-[10px] tracking-[0.1em] font-bold"
            style={{ width: "min(100%, 260px)" }}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            <span className="text-left" style={{ color: "#FF9933" }}>PAST</span>
            <span className="text-center text-white">PRESENT</span>
            <span className="text-right" style={{ color: "#138808" }}>FUTURE</span>
          </motion.div>

          {/* Eyebrow + honest H1 + honest subline */}
          <motion.div
            className="space-y-3"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            <p className="text-[10px] sm:text-[11px] font-mono tracking-[0.25em] text-accent-gold/70 uppercase">
              Glass Box · Transparent Algo Trading
            </p>
            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-[1.05]">
              Backtest nahi.<br />
              <span className="bg-gradient-to-b from-[#FFD700] to-[#00FF88] bg-clip-text text-transparent">
                Proof.
              </span>
            </h1>
            <p className="text-[13px] sm:text-sm text-foreground/85 leading-relaxed max-w-md mx-auto lg:mx-0">
              Har signal ko ek transparent AI conviction score milta hai — threshold paar kare tabhi trade. Har live trade aapke apne broker ke real order se verified.
            </p>
            <p className="text-[11px] text-muted-foreground font-mono tracking-[0.1em]">
              20 yrs NSE data · 6 broker APIs · AWS Mumbai
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
              Poora verified Track Record dekho →
            </Link>
            <p className="text-[10px] text-muted-foreground/60 leading-relaxed max-w-md mx-auto lg:mx-0">
              risk return ke barabar saamne · in-sample backtest labelled hypothetical
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
            aria-label="Learn what these mantras mean"
          >
            <p
              lang="hi"
              className="text-[13px] tracking-[0.18em] text-accent-gold/60 group-hover:text-accent-gold/80 font-serif transition-colors"
            >
              ॐ · <HighlightTri prefix="त्रि" rest="काल" /> ·{" "}
              <HighlightTri prefix="त्रि" rest="शूल" /> ·{" "}
              <HighlightTri prefix="त्रि" rest="स्केलियन" /> · कालचक्र
            </p>
            <p className="text-[10px] tracking-[0.25em] text-muted-foreground/70 group-hover:text-muted-foreground font-mono transition-colors">
              <HighlightTri prefix="TRI" rest="KALA" /> ·{" "}
              <HighlightTri prefix="TRI" rest="SHUL" /> ·{" "}
              <HighlightTri prefix="TRI" rest="SKELION" /> · KALACHAKRA
            </p>
            <p className="text-[9px] tracking-[0.3em] text-accent-gold/50 group-hover:text-accent-gold/90 font-mono pt-1 uppercase transition-colors">
              ✨ Tap to decode
            </p>
          </motion.button>

          {/* Honest, substantiable badges */}
          <motion.div
            className="flex items-center justify-center lg:justify-start gap-2 flex-wrap"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.8 }}
          >
            <span className="text-[9px] tracking-widest px-2 py-1 rounded-full border border-white/30 text-white/90 bg-white/5">
              WHITE-BOX
            </span>
            <span className="text-[9px] tracking-widest px-2 py-1 rounded-full border" style={{ borderColor: "rgba(255, 153, 51, 0.5)", color: "#FF9933", backgroundColor: "rgba(255, 153, 51, 0.1)" }}>
              AAPKA BROKER · AAPKE FUNDS
            </span>
            <span className="text-[9px] tracking-widest px-2 py-1 rounded-full border border-profit/40 text-profit bg-profit/10">
              SEBI-AWARE
            </span>
            <span className="text-[9px] tracking-widest px-2 py-1 rounded-full border border-accent-blue/40 text-accent-blue bg-accent-blue/10">
              ENCRYPTED
            </span>
          </motion.div>
        </motion.div>

        {/* RIGHT — login card */}
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="w-full max-w-md mx-auto lg:ml-auto"
        >
          <div className="glass p-7 sm:p-8 space-y-6 relative rounded-3xl">
            <div className="text-center space-y-1">
              <h2 className="text-lg font-semibold text-foreground">Login</h2>
              <p className="text-xs text-muted-foreground">
                Apne TRADETRI account mein wapas aao
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground/80">
                  Email
                </label>
                <Input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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
                    placeholder="Enter password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="bg-muted/50 border-border h-11 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label={showPassword ? "Hide password" : "Show password"}
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
                {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : "Login"}
              </GlowButton>
            </form>

            {/* Links */}
            <div className="text-center space-y-2 text-sm">
              <p className="text-muted-foreground">
                Don&apos;t have an account?{" "}
                <Link
                  href="/register"
                  className="text-accent-blue hover:underline font-medium"
                >
                  Register
                </Link>
              </p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Footer — honest risk disclaimer + Vadodara line */}
      <footer className="relative w-full max-w-3xl mt-10 space-y-3">
        <p className="text-[10px] leading-relaxed text-muted-foreground/55 text-center">
          Trading mein capital loss ka substantial risk hai. Past performance future results ki guarantee nahi deta — yeh investment advice nahi hai. TRADETRI white-box strategies deta hai; koi guaranteed return claim nahi. Trades aapke apne exchange-registered broker se route hote hain, SEBI ke algo-trading framework ke anusaar.
        </p>
        <p className="text-center text-[10px] text-muted-foreground/60 tracking-wider">
          PRODUCTION GRADE · ENCRYPTED · BUILT IN VADODARA 🇮🇳
        </p>
      </footer>

      <MantrasModal open={mantrasOpen} onClose={() => setMantrasOpen(false)} />
    </div>
  );
}
