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
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-accent-blue/5 via-transparent to-accent-purple/5" />

      {/* Hypnotic full-page Kalachakra mandala */}
      <div className="fixed inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
        <img
          src="/tradetri-hero.svg"
          alt=""
          aria-hidden="true"
          className="max-h-[95vh] w-auto h-auto max-w-[95vw] opacity-[0.22] select-none"
        />
      </div>
      {/* Darkening vignette — deepens edges, spotlights center */}
      <div className="fixed inset-0 pointer-events-none bg-gradient-radial from-transparent via-black/30 to-black/70" style={{ background: "radial-gradient(ellipse at center, transparent 20%, rgba(0,0,0,0.4) 60%, rgba(0,0,0,0.8) 100%)" }} />

      <motion.div
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="relative w-full max-w-md"
      >
        <div className="p-8 space-y-8 relative backdrop-blur-[3px] rounded-3xl">
          {/* Amber glow aura behind logo */}
          

          {/* Logo + Tagline — staggered entrance */}
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
              className="relative font-mono text-[10px] tracking-[0.1em] font-bold"
              style={{ height: "14px", marginTop: "-18px" }}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
            >
              <span className="absolute" style={{ color: "#FF9933", left: "133px" }}>PAST</span>
              <span className="absolute text-white" style={{ left: "176px" }}>PRESENT</span>
              <span className="absolute" style={{ color: "#138808", left: "244px" }}>FUTURE</span>
            </motion.div>

            <motion.div
              className="space-y-1"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
            >
              <p className="text-[13px] text-foreground/90 font-medium tracking-wide">
                India&apos;s First Deep-Learning Trading Engine
              </p>
              <p className="text-[11px] text-muted-foreground font-mono tracking-[0.1em]">
                20 yrs NSE data · 6 broker APIs · AWS Mumbai
              </p>
            </motion.div>

            {/* Sanskrit cultural signature */}
            <motion.button
              type="button"
              onClick={() => setMantrasOpen(true)}
              className="pt-1 space-y-1 group cursor-pointer mx-auto block"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.6 }}
              aria-label="Learn what these mantras mean"
            >
              <p className="text-[13px] tracking-[0.18em] text-accent-gold/90 group-hover:text-accent-gold font-serif transition-colors">
                ॐ · कालचक्र · त्रिकाल · त्रिशूल · त्रिस्केलियन
              </p>
              <p className="text-[10px] tracking-[0.25em] text-muted-foreground/70 group-hover:text-muted-foreground font-mono transition-colors">
                KALACHAKRA · TRIKALA · TRISHUL · TRISKELION
              </p>
              <p className="text-[9px] tracking-[0.3em] text-accent-gold/50 group-hover:text-accent-gold/90 font-mono pt-1 uppercase transition-colors">
                ✨ Tap to decode
              </p>
            </motion.button>

            {/* Trust badges */}
            <motion.div
              className="flex items-center justify-center gap-2 pt-2 flex-wrap"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.75 }}
            >
              <span className="text-[9px] tracking-widest px-2 py-1 rounded-full border border-accent-purple/40 text-accent-purple bg-accent-purple/10">
                AI-POWERED
              </span>
              <span className="text-[9px] tracking-widest px-2 py-1 rounded-full border text-white/90" style={{ borderColor: "rgba(255, 153, 51, 0.5)", color: "#FF9933", backgroundColor: "rgba(255, 153, 51, 0.1)" }}>
                15-LAYER SECURE
              </span>
              <span className="text-[9px] tracking-widest px-2 py-1 rounded-full border border-white/30 text-white/90 bg-white/5">
                SUB-50MS TARGET
              </span>
              <span className="text-[9px] tracking-widest px-2 py-1 rounded-full border border-profit/40 text-profit bg-profit/10">
                SEBI AWARE
              </span>
            </motion.div>
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

        {/* Footer */}
        <MantrasModal open={mantrasOpen} onClose={() => setMantrasOpen(false)} />

        <p className="text-center text-[10px] text-muted-foreground/60 mt-6 tracking-wider">
          PRODUCTION GRADE · ENCRYPTED · BUILT IN VADODARA 🇮🇳
        </p>
      </motion.div>
    </div>
  );
}
