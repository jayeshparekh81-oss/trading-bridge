/**
 * The journey line + the "Aur seekhein" one-line explanations — copy helpers
 * over lib/simple/level.ts. Guidance only: nothing here gates anything.
 */

import type { Lang } from "@/contexts/LanguageContext";
import { t, type SimpleCopyKey } from "@/lib/simple/copy";
import { progressFor, type LearnTileId, type ReqKey, type UiLevel, type UnlockFacts } from "@/lib/simple/level";

export function reqLabel(lang: Lang, k: ReqKey): string {
  return t(lang, `req_${k}` as SimpleCopyKey);
}

/** "Aapka safar: 1 / 4 kadam" + "Agla: Broker jodo". */
export function buildProgress(lang: Lang, level: UiLevel, facts: UnlockFacts): { done: number; total: number; next: string | null } {
  const p = progressFor(level, facts);
  return { done: p.done, total: p.total, next: p.next ? reqLabel(lang, p.next) : null };
}

const TIP_KEY: Record<LearnTileId, SimpleCopyKey> = {
  templates: "tip_templates",
  build: "tip_build",
  pro: "tip_pro",
};

/** AlgoMitra's one line for the first tap on an "Aur seekhein" tile. */
export function tipFor(lang: Lang, id: LearnTileId): string {
  return `${t(lang, "nudge_prefix")}: ${t(lang, TIP_KEY[id])}`;
}
