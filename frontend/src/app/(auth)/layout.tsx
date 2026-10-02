import type { ReactNode } from "react";

import { LanguageSwitch } from "@/components/site/language-switch";

/**
 * The two auth doors (/login, /register) — one column, no chrome. The ONE addition (founder,
 * 2 Oct 2026): the language switch top-right, so a first-timer meets it on the very first screen
 * and never has to hunt for it in settings. Nothing else about the doors changes here.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative">
      <div className="absolute right-3 top-3 z-20">
        <LanguageSwitch id="auth-language-switch" />
      </div>
      {children}
    </div>
  );
}
