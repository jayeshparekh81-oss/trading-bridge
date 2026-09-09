"use client";

/**
 * The ONE owner of the tracking cut-off — the date from which the platform's
 * record starts.
 *
 * ⚠️ READ BEFORE CHANGING ANYTHING HERE. Every sentence this module produces
 * names a DATE to a customer looking at their own money. The date must come
 * from the server on every render; a literal in this file (or in a component)
 * would keep printing a stale, confident number the day the platform moves
 * the cut-off, and nobody would notice because nothing would break.
 *
 * WHERE THE DATE COMES FROM
 * ─────────────────────────
 * `GET /api/system/mode` → `tracking_epoch`, an ISO 8601 instant, e.g.
 * "2026-09-01T00:00:00+05:30". `null` — and an OLDER backend that does not
 * serialise the field at all — both mean "this platform is not applying a
 * cut-off", and both must print NOTHING.
 *
 * THREE STATES, AND THE THIRD ONE IS SILENCE (the paper-banner lesson)
 * ───────────────────────────────────────────────────────────────────
 * `src/lib/paper-mode.ts` exists because a screen named a state it had not
 * read. The same discipline applies to a date:
 *
 *   epoch read      → say it, exactly as the server gave it
 *   epoch is null   → there is no cut-off to disclose; say nothing
 *   epoch unknown   → we have not read it (loading, offline, older backend);
 *                     say nothing. NEVER a fallback date.
 *
 * "We could not read the cut-off" and "the record starts on 1 Sept" are
 * different facts, and only one of them is safe to print.
 *
 * WHY IST, NOT THE BROWSER'S TIMEZONE
 * ───────────────────────────────────
 * The cut-off is a boundary in the INDIAN trading day. Rendering
 * "2026-09-01T00:00:00+05:30" in a UTC browser would print "31 Aug" — the
 * wrong date, on the sentence whose whole job is to state the right one. So
 * the label is always computed in IST (UTC+5:30, no DST), the same rule
 * `istDateKey` in `lib/pnl-tracker.ts` uses for every "aaj" on the platform.
 */

import { useMemo } from "react";

import { useSystemMode } from "@/hooks/useSystemMode";

/** Asia/Kolkata is UTC+5:30 and has no DST. */
const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000;

/**
 * Month names as the founder's copy spells them ("Sept", not "Sep").
 *
 * Deliberately a table rather than `toLocaleDateString`: the ICU short-month
 * spelling for en-IN/en-GB has changed between runtimes ("Sep" → "Sept"), so
 * the rendered copy would silently differ between a customer's browser and
 * the tests. These are month NAMES — the vocabulary of the sentence, not the
 * date. The day, the month and the year are all read from the server.
 */
const MONTH_NAMES = [
  "Jan",
  "Feb",
  "March",
  "April",
  "May",
  "June",
  "July",
  "Aug",
  "Sept",
  "Oct",
  "Nov",
  "Dec",
] as const;

/** The IST calendar parts of an ISO instant, or null when it is unreadable. */
function istParts(iso: string | null | undefined): { day: number; month: number; year: number } | null {
  if (typeof iso !== "string" || iso.trim() === "") return null;
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return null;
  const ist = new Date(ms + IST_OFFSET_MS);
  return { day: ist.getUTCDate(), month: ist.getUTCMonth(), year: ist.getUTCFullYear() };
}

/**
 * The full label the disclosure line uses — day, month, year, in IST.
 * Returns null for anything we cannot read, so the caller renders nothing.
 */
export function formatTrackingEpoch(iso: string | null | undefined): string | null {
  const p = istParts(iso);
  if (!p) return null;
  return `${p.day} ${MONTH_NAMES[p.month]} ${p.year}`;
}

/**
 * The short label the empty states use — day and month only, because the
 * founder's copy says "1 Sept ke baad", not "1 Sept 2026 ke baad". Same
 * server value, one less part; still nothing hardcoded.
 */
export function formatTrackingEpochShort(iso: string | null | undefined): string | null {
  const p = istParts(iso);
  if (!p) return null;
  return `${p.day} ${MONTH_NAMES[p.month]}`;
}

/** The disclosure line, in the founder's words. `label` comes from the server. */
export function trackingNoteText(label: string): string {
  return `Record ${label} se — usse pehle ka data archive mein hai.`;
}

/** The per-strategy empty line, in the founder's words. */
export function noTradesSinceText(shortLabel: string): string {
  return `Is strategy ne ${shortLabel} ke baad abhi tak koi trade nahi kiya.`;
}

/**
 * The "since the cut-off" frame every empty headline shares, so four pages
 * cannot drift into four different sentences. `tail` is the page's own noun
 * phrase, e.g. "abhi tak koi trade nahi hui".
 */
export function sinceEpochHeadline(shortLabel: string, tail: string): string {
  return `${shortLabel} ke baad ${tail}`;
}

/** The one clause that explains where the older rows went. */
export const ARCHIVE_HINT = "Usse pehle ka data archive mein hai.";

/**
 * Is this timestamp at or after the cut-off?
 *
 * `null` means UNKNOWN — no epoch, or a timestamp we cannot parse — and an
 * unknown never counts as either side of the boundary. The caller must treat
 * null as "cannot say", not as false.
 */
export function isSinceEpoch(
  timestamp: string | null | undefined,
  epochIso: string | null | undefined,
): boolean | null {
  if (typeof epochIso !== "string" || typeof timestamp !== "string") return null;
  const epochMs = Date.parse(epochIso);
  const tsMs = Date.parse(timestamp);
  if (!Number.isFinite(epochMs) || !Number.isFinite(tsMs)) return null;
  return tsMs >= epochMs;
}

export interface TrackingEpoch {
  /** The raw ISO instant from the server, or null when there is no cut-off to name. */
  iso: string | null;
  /** "1 Sept 2026" — the disclosure line's date. null → render nothing. */
  label: string | null;
  /** "1 Sept" — the empty states' date. null → render nothing. */
  shortLabel: string | null;
}

const NOTHING_TO_SAY: TrackingEpoch = { iso: null, label: null, shortLabel: null };

/**
 * THE fact owner. Every surface that mentions the cut-off reads it here, so
 * two screens cannot name two different dates (ADR 0001 §2).
 *
 * `useSystemMode` returns null while loading and on persistent failure, and an
 * older backend simply omits `tracking_epoch` — all three collapse to "say
 * nothing", which is the only honest thing an unread date can say.
 */
export function useTrackingEpoch(): TrackingEpoch {
  const mode = useSystemMode();
  const iso = mode?.tracking_epoch ?? null;

  return useMemo(() => {
    if (typeof iso !== "string") return NOTHING_TO_SAY;
    const label = formatTrackingEpoch(iso);
    const shortLabel = formatTrackingEpochShort(iso);
    // An unparseable value is not a date we may print.
    if (!label || !shortLabel) return NOTHING_TO_SAY;
    return { iso, label, shortLabel };
  }, [iso]);
}

export default useTrackingEpoch;
