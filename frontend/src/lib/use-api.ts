"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";

interface UseApiResult<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Fetch data from API with loading/error states + auto-refresh.
 *
 * @param url       API endpoint (e.g. "/users/me/trades")
 * @param fallback  Fallback data when API is unavailable
 * @param interval  Auto-refresh interval in ms (0 = disabled)
 */
export function useApi<T>(
  url: string | null,
  fallback?: T | null,
  interval = 0,
): UseApiResult<T> {
  const [data, setData] = useState<T | null>(fallback ?? null);
  const [isLoading, setIsLoading] = useState(!!url);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    if (!url) return;
    setIsLoading((prev) => !data ? true : prev); // only show spinner on first load
    setError(null);

    try {
      const result = await api.get<T>(url);
      if (mountedRef.current) {
        setData(result);
        setIsLoading(false);
      }
    } catch (err) {
      if (mountedRef.current) {
        const msg = err instanceof ApiError ? err.detail : "Something went wrong";
        setError(msg);
        setIsLoading(false);
        // Keep fallback data visible if available
        if (fallback && !data) setData(fallback);
      }
    }
  }, [url]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    mountedRef.current = true;
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

  return { data, isLoading, error, refetch: fetchData };
}
