/**
 * Visible-but-locked tiles + the journey line (founder, 2026-09-05 evening):
 * a locked level is shown greyed with a 🔒 and ONE plain line of what opens
 * it, computed from the customer's ACTUAL facts — so a Pro account that
 * switched to Simple sees what it has really done, not a fresh-account zero.
 */

import type { Lang } from "@/contexts/LanguageContext";
import { t, type SimpleCopyKey } from "@/lib/simple/copy";
import {
  TILE_LEVEL,
  TILE_TITLE_KEY,
  lockedTilesFor,
  progressFor,
  remainingFor,
  type ReqKey,
  type TileId,
  type UiLevel,
  type UnlockFacts,
} from "@/lib/simple/level";

export interface LockedTileCopy {
  id: TileId | "pro";
  title: string;
  hint: string;
}

export function reqLabel(lang: Lang, k: ReqKey): string {
  return t(lang, `req_${k}` as SimpleCopyKey);
}

/** "Broker jodo + pehla signal dekho, phir yeh khulega" — only what is still missing. */
export function lockedHint(lang: Lang, need: 2 | 3 | 4, facts: UnlockFacts): string {
  const steps = remainingFor(need, facts).map((k) => reqLabel(lang, k)).join(" + ");
  return t(lang, "locked_then", { steps });
}

/** Every tile above `level`, greyed with its one-line hint, plus the Pro tile. */
export function buildLocked(lang: Lang, level: UiLevel, facts: UnlockFacts): LockedTileCopy[] {
  return [
    ...lockedTilesFor(level).map((id) => ({
      id,
      title: t(lang, TILE_TITLE_KEY[id] as SimpleCopyKey),
      hint: lockedHint(lang, TILE_LEVEL[id] as 2 | 3 | 4, facts),
    })),
    { id: "pro" as const, title: t(lang, "locked_pro_title"), hint: t(lang, "locked_pro_hint") },
  ];
}

/** "Aapka safar: 1 / 4 kadam" + "Agla: Broker jodo". */
export function buildProgress(lang: Lang, level: UiLevel, facts: UnlockFacts): { done: number; total: number; next: string | null } {
  const p = progressFor(level, facts);
  return { done: p.done, total: p.total, next: p.next ? reqLabel(lang, p.next) : null };
}
