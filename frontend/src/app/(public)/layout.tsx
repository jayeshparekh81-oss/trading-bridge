"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Menu, X } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/logo";
import type { ReactNode } from "react";

const navLinks = [
  { label: "Features", href: "/home#features" },
  { label: "Track Record", href: "/showcase" },
  { label: "Pricing", href: "/pricing" },
  { label: "About", href: "/about" },
  { label: "Contact", href: "/contact" },
];

function PublicNav() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "fixed top-0 left-0 right-0 z-50 transition-all duration-300",
        scrolled ? "bg-background/90 backdrop-blur-lg border-b border-border" : "bg-transparent"
      )}
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between h-16 px-4 md:px-6">
        <Link href="/home" className="flex items-center gap-2">
          <Logo variant="icon" width={32} height={32} priority />
          <Logo variant="wordmark" height={26} />
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <Link href="/login" className="text-sm font-medium hover:text-foreground transition-colors text-muted-foreground">Login</Link>
          <Link
            href="/register"
            className="px-5 py-2 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-[0_0_25px_rgba(59,130,246,0.4)] transition-all"
          >
            Start Free &rarr;
          </Link>
        </div>

        {/* Mobile toggle */}
        <button className="md:hidden p-2" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Menu">
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="md:hidden bg-background/95 backdrop-blur-lg border-b border-border px-4 pb-4"
        >
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href} className="block py-2.5 text-sm text-muted-foreground" onClick={() => setMobileOpen(false)}>
              {link.label}
            </Link>
          ))}
          <div className="flex gap-3 mt-3">
            <Link href="/login" className="flex-1 text-center py-2 rounded-lg border border-border text-sm">Login</Link>
            <Link href="/register" className="flex-1 text-center py-2 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple">Start Free</Link>
          </div>
        </motion.div>
      )}
    </header>
  );
}

function PublicFooter() {
  // Only links to pages that actually exist — no dead <span> links.
  const cols = [
    {
      title: "Product",
      links: [
        { label: "Features", href: "/home#features" },
        { label: "Pricing", href: "/pricing" },
        { label: "Track Record", href: "/showcase" },
      ],
    },
    {
      title: "Company",
      links: [
        { label: "About", href: "/about" },
        { label: "Contact", href: "/contact" },
      ],
    },
    {
      title: "Legal",
      links: [
        { label: "Terms", href: "/terms" },
        { label: "Privacy", href: "/privacy" },
        { label: "Disclaimer", href: "/disclaimer" },
        { label: "SEBI Info", href: "/sebi" },
      ],
    },
  ];

  return (
    <footer className="border-t border-border bg-background/50">
      <div className="max-w-7xl mx-auto px-4 md:px-6 py-12">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8">
          <div className="col-span-2">
            <Link href="/home" className="flex items-center gap-2 mb-3">
              <Logo variant="icon" width={28} height={28} />
              <Logo variant="wordmark" height={22} />
            </Link>
            <p className="text-xs text-muted-foreground max-w-xs">
              Transparent, white-box algo trading. Built in India.
            </p>
          </div>
          {cols.map((col) => (
            <div key={col.title}>
              <h4 className="font-semibold text-sm mb-3">{col.title}</h4>
              <ul className="space-y-2">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
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
