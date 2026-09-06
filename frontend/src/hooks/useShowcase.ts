"use client";

/**
 * ONE data source for every strategy card — public Track Record, in-app
 * Marketplace, "Strategy chuno", listing detail (founder, 2026-09-05:
 * "one thing never lives in two places two different ways").
 *
 *   GET /showcase              masked list (S1/S2/S3, headline NET stats)
 *   GET /showcase/{key}        backtest detail (in-sample, non-compounded, NET)
 *   GET /showcase/{key}/live   live-record state + the published listing_id
 *
 * The showcase endpoints are public and masked; the app joins them to its
 * marketplace listing by `listing_id` — it never unmasks anything.
 */

import { useEffect, useMemo, useState } from "react";
import { api } from "@/shared/api/client";
import { useApi } from "@/shared/api/use-api";
import type { LiveRecord, ShowcaseDetail, ShowcaseListItem, ShowcaseListResponse } from "@/lib/showcase/data";

export interface StrategyCardFeed {
  detail: ShowcaseDetail | null;
  live: LiveRecord | null;
  loading: boolean;
}

/** Detail + live record for one showcase key (null key = nothing to fetch). */
export function useStrategyCardData(key: string | null): StrategyCardFeed {
  const detail = useApi<ShowcaseDetail>(key ? `/showcase/${key}` : null);
  const live = useApi<LiveRecord>(key ? `/showcase/${key}/live` : null);
  return useMemo(
    () => ({ detail: detail.data ?? null, live: live.data ?? null, loading: !!key && (detail.isLoading || live.isLoading) }),
    [detail.data, detail.isLoading, live.data, live.isLoading, key],
  );
}

export interface ShowcaseIndexEntry {
  item: ShowcaseListItem;
  live: LiveRecord | null;
}

export interface ShowcaseIndex {
  items: ShowcaseListItem[];
  /** showcase key → entry */
  byKey: Record<string, ShowcaseIndexEntry>;
  /** published marketplace listing id → entry (only strategies with a listing) */
  byListingId: Record<string, ShowcaseIndexEntry>;
  loading: boolean;
  error: string | null;
}

/**
 * The whole showcase, indexed both ways. The app's Marketplace uses
 * `byListingId` to put the SAME proof numbers on a listing that the public
 * Track Record shows; the detail page uses it to find a listing's key.
 */
export function useShowcaseIndex(enabled = true): ShowcaseIndex {
  const list = useApi<ShowcaseListResponse>(enabled ? "/showcase" : null);
  const items = useMemo(() => list.data?.strategies ?? [], [list.data]);
  // Live records are keyed by the list's key-set so "loading" is DERIVED
  // (keys changed, records not yet fetched) — no setState inside the effect.
  const [lives, setLives] = useState<{ keys: string; map: Record<string, LiveRecord | null> }>({ keys: "", map: {} });

  const keys = items.map((s) => s.key).join(",");
  useEffect(() => {
    if (!keys) return;
    let alive = true;
    Promise.all(
      keys.split(",").map(async (k) => {
        try {
          return [k, await api.get<LiveRecord>(`/showcase/${k}/live`)] as const;
        } catch {
          return [k, null] as const;
        }
      }),
    ).then((pairs) => {
      if (alive) setLives({ keys, map: Object.fromEntries(pairs) });
    });
    return () => {
      alive = false;
    };
  }, [keys]);
  const livesLoading = !!keys && lives.keys !== keys;

  return useMemo(() => {
    const liveMap = lives.keys === keys ? lives.map : {};
    const byKey: Record<string, ShowcaseIndexEntry> = {};
    const byListingId: Record<string, ShowcaseIndexEntry> = {};
    for (const item of items) {
      const live = liveMap[item.key] ?? null;
      const entry = { item, live };
      byKey[item.key] = entry;
      if (live?.listing_id) byListingId[live.listing_id] = entry;
    }
    return { items, byKey, byListingId, loading: list.isLoading || livesLoading, error: list.error ?? null };
  }, [items, lives, keys, list.isLoading, list.error, livesLoading]);
}
