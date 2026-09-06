"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./client";

interface UseApiResult<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  /**
   * True iff the last COMPLETED fetch failed with a 402 PLAN_REQUIRED (B3
   * paywall). Reactive signal for the upgrade walls — NEVER set proactively
   * from plan_status, only from an actual backend 402. False when the flag is
   * OFF (backend returns no 402s), so walls stay dormant.
   *
   * "Completed" is load-bearing: the value is held across an in-flight
   * refresh, so a polling surface cannot blink the wall open between
   * responses. See the note in ``fetchData``.
   */
  paywalled: boolean;
  /** Server-driven upgrade URL from the 402 detail (B3.0 contract); null when
   *  not paywalled. Walls use it for the CTA, falling back to /pricing. */
  paywallUrl: string | null;
  refetch: () => void;
}

/** Pull a human-readable string out of an ApiError whose ``detail`` may be a
 *  structured paywall object ({code, message, upgrade_url}) rather than text. */
function errorMessage(err: ApiError): string {
  const detail = err.detail as unknown;
  if (typeof detail === "string") return detail;
  if (
    detail &&
    typeof detail === "object" &&
    "message" in detail &&
    typeof (detail as { message: unknown }).message === "string"
  ) {
    return (detail as { message: string }).message;
  }
  return `Request failed (${err.status})`;
}

/** Extract the B3 paywall signal from a 402 ApiError: a paywall ONLY when the
 *  structured detail carries code PLAN_REQUIRED (defensive against any
 *  unrelated 402). Also returns the server-driven upgrade_url. */
function paywallInfo(err: ApiError): { paywalled: boolean; url: string | null } {
  if (err.status !== 402) return { paywalled: false, url: null };
  const detail = (err.data as { detail?: { code?: string; upgrade_url?: string } } | undefined)
    ?.detail;
  if (detail?.code !== "PLAN_REQUIRED") return { paywalled: false, url: null };
  return { paywalled: true, url: detail.upgrade_url ?? null };
}

/**
 * Fetch data from API with loading/error states + auto-refresh.
 *
 * @param url       API endpoint (e.g. "/users/me/trades")
 * @param fallback  Fallback data when API is unavailable
 * @param interval  Auto-refresh interval in ms (0 = disabled)
 */
export function useApi<T>(url: string | null, fallback?: T | null, interval = 0): UseApiResult<T> {
  const [data, setData] = useState<T | null>(fallback ?? null);
  const [isLoading, setIsLoading] = useState(!!url);
  const [error, setError] = useState<string | null>(null);
  // Initial value is not-paywalled on purpose: before the first response there
  // is no "last known" state to hold, and a wall must never be armed by
  // anything other than a real backend 402 (the flag is OFF in production, so
  // no 402s arrive and every wall stays dormant).
  const [paywalled, setPaywalled] = useState(false);
  const [paywallUrl, setPaywallUrl] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    if (!url) return;
    setIsLoading((prev) => (!data ? true : prev)); // only show spinner on first load
    // ``error`` / ``paywalled`` / ``paywallUrl`` are deliberately NOT cleared
    // here. Clearing them before the await made every refresh blink the state
    // off for the whole round-trip: on /signals (15s poll) a paywalled
    // customer's "Premium" chip turned into an ARMED one-click confirm button
    // once per interval, and the UpgradeWall vanished with it. The last known
    // state is held until the NEW response says otherwise — cleared on a
    // success below, and in the catch on any failure that is not a 402
    // PLAN_REQUIRED.

    try {
      const result = await api.get<T>(url);
      if (mountedRef.current) {
        setData(result);
        setError(null);
        setPaywalled(false);
        setPaywallUrl(null);
        setIsLoading(false);
      }
    } catch (err) {
      if (mountedRef.current) {
        const apiErr = err instanceof ApiError ? err : null;
        const pay = apiErr ? paywallInfo(apiErr) : { paywalled: false, url: null };
        // A 402 ARMS the wall. Any other failure tells us nothing about
        // entitlement, so it must HOLD the last known state rather than clear
        // it — a transient 500 or a dropped connection is not evidence that
        // the customer has paid. Clearing here would re-open the exact hole
        // this fix closes, just triggered by a network blip instead of by
        // every poll: on /signals that means an ARMED one-click order button.
        // The wall is only ever cleared by a SUCCESSFUL response (above).
        // Failing closed costs a paid customer one retry; failing open hands
        // an unpaid customer a live order control.
        if (pay.paywalled) {
          setPaywalled(true);
          setPaywallUrl(pay.url);
        }
        setError(apiErr ? errorMessage(apiErr) : "Something went wrong");
        setIsLoading(false);
        // Keep fallback data visible if available
        if (fallback && !data) setData(fallback);
      }
    }
  }, [url]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    mountedRef.current = true;
    // Fetch-on-mount: fetchData() sets loading synchronously before its first
    // await. Intentional data-fetching pattern (pre-dates B3.4); the rule's
    // cascading-render concern doesn't apply to a one-shot mount fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchData();

    let timer: ReturnType<typeof setInterval> | undefined;
    if (interval > 0) {
      timer = setInterval(fetchData, interval);
    }

    return () => {
      mountedRef.current = false;
      if (timer) clearInterval(timer);
    };
  }, [fetchData, interval]);

  return { data, isLoading, error, paywalled, paywallUrl, refetch: fetchData };
}
