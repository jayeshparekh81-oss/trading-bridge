/**
 * SiteFooter — compact site-wide disclaimer strip, mounted at the
 * root layout. Always visible at the bottom of the viewport (the
 * root <body> is flex-col with min-h-full, so a single footer
 * naturally sticks below the content).
 *
 * Language follows THE ONE choice (contexts/LanguageContext) through
 * `useLegacyLang()`: English on the server render and whenever no choice
 * is stored; the Hinglish copy only when the customer chose Hinglish.
 * (2 Oct 2026: it used to default to "hi" and read its own `tradetri_lang`
 * key, so a first visitor got an English page with a Hinglish footer —
 * the founder's rule 5 broken on the live site. The key is never read here
 * any more; a stale `tradetri_lang` on a device cannot flip this strip.)
 */

"use client";

import Link from "next/link";

import { useLegacyLang } from "@/contexts/LanguageContext";
import { FOOTER_COPY } from "@/lib/compliance/disclaimer-text";
import { useAuthOptional } from "@/lib/auth";

export function SiteFooter() {
  const lang = useLegacyLang();
  // The long-form page lives inside the app; a logged-out visitor gets the public /disclaimer instead of a login bounce.
  const user = useAuthOptional()?.user ?? null;

  return (
    <footer
      data-testid="site-footer"
      data-lang={lang}
      className="mt-auto w-full border-t border-white/5 bg-neutral-950/80 supports-backdrop-filter:backdrop-blur-md px-4 py-3 text-11 leading-relaxed text-neutral-500"
    >
      <div className="mx-auto flex max-w-6xl flex-col items-start gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <p data-testid="site-footer-disclaimer" className="flex-1">
          {lang === "hi" ? FOOTER_COPY.hi : FOOTER_COPY.en}
        </p>
        <Link
          href={user ? "/compliance/legal" : "/disclaimer"}
          data-testid="site-footer-cta"
          className="shrink-0 whitespace-nowrap text-emerald-400 underline-offset-2 hover:underline"
        >
          {lang === "hi" ? FOOTER_COPY.cta_hi : FOOTER_COPY.cta_en} →
        </Link>
      </div>
    </footer>
  );
}
