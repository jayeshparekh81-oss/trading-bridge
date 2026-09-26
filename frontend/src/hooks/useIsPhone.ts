"use client";

import { useEffect, useState } from "react";

/**
 * True on a phone-width screen (below Tailwind's md, 768px). A table with a dozen
 * columns is swapped for stacked cards there (founder's rule, 26 Sep, point 7:
 * "nothing cut off at 375px"). Starts FALSE — the server render and any screen
 * we cannot measure get the full table, never a guess.
 */
export const PHONE_QUERY = "(max-width: 767px)";

export function useIsPhone(): boolean {
  const [phone, setPhone] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(PHONE_QUERY);
    const sync = () => setPhone(mq.matches);
    sync();
    mq.addEventListener?.("change", sync);
    return () => mq.removeEventListener?.("change", sync);
  }, []);
  return phone;
}
