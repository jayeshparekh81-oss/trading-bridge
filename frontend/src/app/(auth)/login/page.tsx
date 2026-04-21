"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Zap, Eye, EyeOff, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { GlowButton } from "@/components/ui/glow-button";
import { useAuth } from "@/lib/auth";
import Link from "next/link";

export default function LoginPage() {
  const { login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
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

      <motion.div
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="relative w-full max-w-md"
      >
        <div className="glass rounded-2xl p-8 space-y-8">
          {/* Logo + Tagline */}
          <div className="text-center space-y-2">
            <div className="flex items-center justify-center gap-2 mb-4">
              <Zap className="h-8 w-8 text-accent-blue" />
              <span className="text-2xl font-bold text-foreground">TRADETRI</span>
            </div>
            <p className="text-sm text-muted-foreground">
              India&apos;s AI-Powered Algo Trading Platform
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

        {/* Footer */}
        <p className="text-center text-xs text-muted-foreground mt-6">
          15-Layer Security &bull; Encrypted &bull; Production Grade
        </p>
      </motion.div>
    </div>
  );
}
