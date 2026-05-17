/**
 * SiteFooter — compact site-wide disclaimer strip, mounted at the
 * root layout. Always visible at the bottom of the viewport (the
 * root <body> is flex-col with min-h-full, so a single footer
 * naturally sticks below the content).
 *
 * Language follows the global `tradetri_lang` localStorage key
 * (same one the onboarding tour + /help page use). Reads on mount
 * and re-renders if changed elsewhere via a `storage` event.
 */

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { FOOTER_COPY } from "@/lib/compliance/disclaimer-text";

const LS_KEY_LANG = "tradetri_lang";

function readLang(): "en" | "hi" {
  if (typeof window === "undefined") return "hi";
  try {
    const raw = window.localStorage.getItem(LS_KEY_LANG);
    return raw === "en" ? "en" : "hi";
  } catch {
    return "hi";
  }
}

export function SiteFooter() {
  const [lang, setLang] = useState<"en" | "hi">("hi");

  useEffect(() => {
    setLang(readLang());
    function onStorage(e: StorageEvent) {
      if (e.key === LS_KEY_LANG) setLang(readLang());
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  return (
    <footer
      data-testid="site-footer"
      data-lang={lang}
      className="mt-auto w-full border-t border-white/5 bg-neutral-950/80 supports-backdrop-filter:backdrop-blur-md px-4 py-3 text-[11px] leading-relaxed text-neutral-500"
    >
      <div className="mx-auto flex max-w-6xl flex-col items-start gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <p data-testid="site-footer-disclaimer" className="flex-1">
          {lang === "hi" ? FOOTER_COPY.hi : FOOTER_COPY.en}
        </p>
        <Link
          href="/compliance/legal"
          data-testid="site-footer-cta"
          className="shrink-0 whitespace-nowrap text-emerald-400 underline-offset-2 hover:underline"
        >
          {lang === "hi" ? FOOTER_COPY.cta_hi : FOOTER_COPY.cta_en} →
        </Link>
      </div>
    </footer>
  );
}
