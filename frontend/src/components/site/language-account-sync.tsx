"use client";

/**
 * THE LANGUAGE IS REMEMBERED PER ACCOUNT, ACROSS LOGOUT/LOGIN (founder, 2 Oct 2026, item 4).
 *
 * Where it lives: `users.notification_prefs._ui_language` — the SAME JSON column and the SAME
 * read-merge-write `PUT /api/users/me` the Simple-mode ladder already uses (hooks/useLadder.tsx).
 * No backend change: `GET /api/auth/me` already returns `notification_prefs`, the PUT already
 * accepts it. The PUT REPLACES the dict wholesale, so every write spreads the server's current
 * prefs first (the ladder, the onboarding keys, the notification toggles) and then re-reads
 * `/auth/me`, so a later Settings save never drops this key.
 *
 * The rules, in order:
 *   1. ACCOUNT WINS. When a user loads whose prefs hold a valid language, that language is applied to
 *      this device (`explicit: false` — never written back).
 *   2. A DEVICE CHOICE made before login (the switch on the public site) is attached to the account
 *      the first time that account loads WITHOUT a stored language.
 *   3. EVERY EXPLICIT CHOICE while logged in is written to the account.
 *   4. No choice anywhere → the default (English) shows and NOTHING is written — "never chose" stays
 *      "never chose" until the customer taps the switch.
 */

import { useEffect, useRef } from "react";

import { isLang, useLanguage, type Lang } from "@/contexts/LanguageContext";
import { useAuthOptional } from "@/lib/auth";
import { api } from "@/shared/api/client";

export const ACCOUNT_LANG_KEY = "_ui_language";

export function readAccountLanguage(prefs: Record<string, unknown> | null | undefined): Lang | null {
  const v = prefs?.[ACCOUNT_LANG_KEY];
  return isLang(v) ? v : null;
}

export function LanguageAccountSync() {
  const auth = useAuthOptional();
  const { lang, hydrated, chosen, choiceSeq, setLang } = useLanguage();
  const user = auth?.user ?? null;
  const appliedFor = useRef<string | null>(null);
  const persistedSeq = useRef(0);
  const inFlight = useRef<Promise<void> | null>(null);

  async function persist(next: Lang) {
    if (!user) return;
    const prefs = { ...(user.notification_prefs ?? {}), [ACCOUNT_LANG_KEY]: next };
    const run = (async () => {
      try {
        await api.put("/users/me", { notification_prefs: prefs });
        await auth?.refreshUser();
      } catch {
        // offline / 5xx — the device still remembers; the next explicit choice retries.
      }
    })();
    inFlight.current = run;
    await run;
  }

  // 1 + 2 + 4: when the account arrives.
  useEffect(() => {
    if (!hydrated) return;
    if (!user) {
      appliedFor.current = null;
      return;
    }
    if (appliedFor.current === user.id) return;
    appliedFor.current = user.id;
    const stored = readAccountLanguage(user.notification_prefs);
    if (stored) {
      persistedSeq.current = choiceSeq;
      if (stored !== lang) setLang(stored, { explicit: false });
      return;
    }
    if (chosen) {
      persistedSeq.current = choiceSeq;
      void persist(lang);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once per account id, by design
  }, [hydrated, user?.id]);

  // 3: every explicit choice while logged in.
  useEffect(() => {
    if (!hydrated || !user) return;
    if (choiceSeq === persistedSeq.current) return;
    persistedSeq.current = choiceSeq;
    void persist(lang);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed on the choice counter, by design
  }, [choiceSeq]);

  return null;
}
