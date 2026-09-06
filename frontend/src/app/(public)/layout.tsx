"use client";

/**
 * Public site chrome — the SHOP WINDOW (founder, 2026-09-05: "Public = shop
 * window only. App = the whole shop.").
 *
 *   nav: Home · Proof · Pricing            (About/Contact live in the footer)
 *   logged out: Login · Start Free →       logged in: one "App kholo →" button
 *
 * Old URLs keep working (/home#features, /about, /contact are still routes).
 * The header is the same HeaderShell the app's TopBar renders.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Menu, X } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "@/components/logo";
import { HeaderLogo, HeaderShell } from "@/components/site/header-shell";
import { useAuth } from "@/lib/auth";
import { PUBLIC_NAV, PUBLIC_FOOTER_COLS } from "@/lib/public-nav";

const CTA_CLASS =
  "px-5 py-2 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-glow-profit transition-all inline-flex items-center gap-1.5";

/** Right-hand buttons: the ONE thing that changes when a visitor is logged in. */
function AuthButtons({ user, onNavigate, stacked = false }: { user: unknown; onNavigate?: () => void; stacked?: boolean }) {
  if (user) {
    return (
      <Link href="/" data-testid="public-open-app" className={stacked ? `${CTA_CLASS} flex-1 justify-center` : CTA_CLASS} onClick={onNavigate}>
        App kholo <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    );
  }
  return (
    <>
      <Link
        href="/login"
        data-testid="public-login"
        className={stacked ? "flex-1 text-center py-2 rounded-lg border border-border text-sm" : "text-sm font-medium hover:text-foreground transition-colors text-muted-foreground"}
        onClick={onNavigate}
      >
        Login
      </Link>
      <Link href="/register" data-testid="public-start-free" className={stacked ? `${CTA_CLASS} flex-1 justify-center` : CTA_CLASS} onClick={onNavigate}>
        Start Free <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </>
  );
}

function PublicNav() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user } = useAuth();

  return (
    <HeaderShell
      position="fixed"
      contained
      testid="public-header"
      left={<HeaderLogo href="/home" />}
      center={
        <nav aria-label="Public" data-testid="public-nav" className="flex items-center gap-8">
          {PUBLIC_NAV.map((link) => (
            <Link key={link.href} href={link.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              {link.label}
            </Link>
          ))}
        </nav>
      }
      right={
        <>
          <div className="hidden md:flex items-center gap-3" data-testid="public-auth">
            <AuthButtons user={user} />
          </div>
          <button className="md:hidden p-2" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Menu" aria-expanded={mobileOpen} data-testid="public-menu">
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </>
      }
      below={
        mobileOpen ? (
          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="md:hidden bg-background/95 backdrop-blur-lg border-b border-border px-4 pb-4" data-testid="public-mobile-menu">
            {PUBLIC_NAV.map((link) => (
              <Link key={link.href} href={link.href} className="block py-2.5 text-sm text-muted-foreground" onClick={() => setMobileOpen(false)}>
                {link.label}
              </Link>
            ))}
            <div className="flex gap-3 mt-3">
              <AuthButtons user={user} stacked onNavigate={() => setMobileOpen(false)} />
            </div>
          </motion.div>
        ) : null
      }
    />
  );
}

function PublicFooter() {
  // Only links to pages that actually exist — no dead <span> links.
  return (
    <footer className="border-t border-border bg-background/50" data-testid="public-footer">
      <div className="max-w-7xl mx-auto px-4 md:px-6 py-12">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8">
          <div className="col-span-2">
            <Link href="/home" className="flex items-center gap-2 mb-3">
              <Logo variant="icon" width={28} height={28} />
              <Logo variant="wordmark" height={22} />
            </Link>
            <p className="text-xs text-muted-foreground max-w-xs">Every signal, every fill — shown. Built in India.</p>
          </div>
          {PUBLIC_FOOTER_COLS.map((col) => (
            <div key={col.title}>
              <h4 className="font-semibold text-sm mb-3">{col.title}</h4>
              <ul className="space-y-2">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-10 pt-6 border-t border-border text-center text-xs text-muted-foreground">
          <span>&copy; 2026 TRADETRI. Made in India {"\u{1F1EE}\u{1F1F3}"}</span>
        </div>
      </div>
    </footer>
  );
}

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <PublicNav />
      <main className="flex-1">{children}</main>
      <PublicFooter />
    </div>
  );
}
