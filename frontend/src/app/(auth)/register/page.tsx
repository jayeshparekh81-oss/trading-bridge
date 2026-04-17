"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Zap, Eye, EyeOff, Check, X, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { GlowButton } from "@/components/ui/glow-button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import Link from "next/link";

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

  if (score <= 1) return { score: 20, label: "Weak", color: "text-loss" };
  if (score <= 2) return { score: 40, label: "Fair", color: "text-accent-gold" };
  if (score <= 3) return { score: 60, label: "Good", color: "text-accent-blue" };
  if (score <= 4) return { score: 80, label: "Strong", color: "text-profit" };
  return { score: 100, label: "Excellent", color: "text-profit" };
}

export default function RegisterPage() {
  const { register } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: "",
  });

  const strength = useMemo(
    () => getPasswordStrength(form.password),
    [form.password]
  );

  const passwordsMatch =
    form.password.length > 0 && form.password === form.confirmPassword;

  const update = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0A0E1A] px-4 py-8">
      <div className="absolute inset-0 bg-gradient-to-br from-accent-purple/5 via-transparent to-accent-blue/5" />

      <motion.div
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6 }}
        className="relative w-full max-w-md"
      >
        <div className="glass rounded-2xl p-8 space-y-6">
          {/* Logo */}
          <div className="text-center space-y-2">
            <div className="flex items-center justify-center gap-2 mb-4">
              <Zap className="h-8 w-8 text-accent-blue" />
              <span className="text-2xl font-bold text-white">TradeForge</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Create your trading account
            </p>
          </div>

          {/* Form */}
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">
                Full Name
              </label>
              <Input
                placeholder="Jayesh Parekh"
                value={form.full_name}
                onChange={(e) => update("full_name", e.target.value)}
                className="bg-white/[0.05] border-white/[0.1] h-11"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">
                Email
              </label>
              <Input
                type="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                className="bg-white/[0.05] border-white/[0.1] h-11"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">
                Phone (optional)
              </label>
              <Input
                type="tel"
                placeholder="+91 98765 43210"
                value={form.phone}
                onChange={(e) => update("phone", e.target.value)}
                className="bg-white/[0.05] border-white/[0.1] h-11"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">
                Password
              </label>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="Min 8 characters"
                  value={form.password}
                  onChange={(e) => update("password", e.target.value)}
                  className="bg-white/[0.05] border-white/[0.1] h-11 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-white"
                  aria-label="Toggle password visibility"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {form.password.length > 0 && (
                <div className="space-y-1.5 mt-2">
                  <Progress value={strength.score} className="h-1.5" />
                  <p className={cn("text-xs font-medium", strength.color)}>
                    {strength.label}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">
                Confirm Password
              </label>
              <div className="relative">
                <Input
                  type="password"
                  placeholder="Re-enter password"
                  value={form.confirmPassword}
                  onChange={(e) => update("confirmPassword", e.target.value)}
                  className="bg-white/[0.05] border-white/[0.1] h-11 pr-10"
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

            <GlowButton
              className="w-full"
              size="lg"
              variant="profit"
              disabled={loading || !form.email || !form.password || !form.full_name || !passwordsMatch}
              onClick={async () => {
                setLoading(true);
                try {
                  await register({
                    email: form.email,
                    password: form.password,
                    full_name: form.full_name,
                    phone: form.phone || undefined,
                  });
                } catch { /* toast shown by auth context */ }
                finally { setLoading(false); }
              }}
            >
              {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : "Create Account"}
            </GlowButton>
          </div>

          <div className="text-center text-sm">
            <p className="text-muted-foreground">
              Already have an account?{" "}
              <Link
                href="/login"
                className="text-accent-blue hover:underline font-medium"
              >
                Login
              </Link>
            </p>
          </div>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-6">
          15-Layer Security &bull; Encrypted &bull; Production Grade
        </p>
      </motion.div>
    </div>
  );
}
