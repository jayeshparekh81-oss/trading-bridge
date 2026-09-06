/**
 * The paywall must not flicker open between polls.
 *
 * ``useApi`` used to clear ``paywalled`` / ``paywallUrl`` / ``error``
 * synchronously before its first await. On a polling surface that means the
 * signal is false for the WHOLE duration of every refresh — and /signals
 * (15s poll) renders the live one-click "Take trade" control whenever
 * ``!paywalled``. A paywalled customer therefore watched the Premium chip
 * turn into an armed, clickable confirm button once per interval, with the
 * UpgradeWall blinking out at the same moment.
 *
 * These tests hold the hook to the rule: the last known state survives an
 * in-flight refresh, and only a NEW response changes it.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ``vi.mock`` is hoisted above the file body, so the spy has to be hoisted
// with it.
const { get } = vi.hoisted(() => ({ get: vi.fn() }));

// Keep the REAL ApiError (the hook does ``err instanceof ApiError``, so the
// class the test throws must be the class the hook imports) and stub only the
// network call.
vi.mock("@/shared/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/api/client")>();
  return { ...actual, api: { ...actual.api, get } };
});

import { ApiError } from "@/shared/api/client";
import { useApi } from "@/shared/api/use-api";

const URL = "/marketplace/subscriptions/signals?status=received";
const POLL_MS = 15_000;

interface SignalFeed {
  signals: { id: string }[];
}

/** A backend 402 exactly as ``client.request`` builds it for the B3 paywall. */
function planRequired(): ApiError {
  const body = {
    detail: {
      code: "PLAN_REQUIRED",
      message: "Premium plan chahiye — one-click confirm band hai.",
      upgrade_url: "/pricing?from=signals",
    },
  };
  return new ApiError(402, body.detail.message, body);
}

/** A promise the test settles by hand, so the in-flight window is observable. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** Let the hook's await + the resulting React updates flush. */
async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  get.mockReset();
  // Any poll the test did not arrange for hangs harmlessly instead of
  // resolving undefined into the hook.
  get.mockImplementation(() => new Promise(() => {}));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useApi paywall flicker", () => {
  it("never blinks open across polling refreshes", async () => {
    const first = deferred<SignalFeed>();
    get.mockImplementationOnce(() => first.promise);

    const { result } = renderHook(() => useApi<SignalFeed>(URL, null, POLL_MS));

    // Before any response there is no "last known" state, and the correct
    // initial value is not-paywalled — walls stay dormant.
    expect(result.current.paywalled).toBe(false);
    expect(result.current.paywallUrl).toBeNull();

    first.reject(planRequired());
    await flush();

    expect(result.current.paywalled).toBe(true);
    expect(result.current.paywallUrl).toBe("/pricing?from=signals");

    // Three more polls, each observed mid-flight — the window where the wall
    // used to blink open.
    for (let poll = 0; poll < 3; poll++) {
      const next = deferred<SignalFeed>();
      get.mockImplementationOnce(() => next.promise);

      await act(async () => {
        vi.advanceTimersByTime(POLL_MS);
      });

      // In flight: the request has gone out, no answer yet.
      expect(result.current.paywalled).toBe(true);
      expect(result.current.paywallUrl).toBe("/pricing?from=signals");

      next.reject(planRequired());
      await flush();

      expect(result.current.paywalled).toBe(true);
      expect(result.current.paywallUrl).toBe("/pricing?from=signals");
    }

    expect(get).toHaveBeenCalledTimes(4);
  });

  it("clears the wall when a later response is a normal success", async () => {
    const first = deferred<SignalFeed>();
    get.mockImplementationOnce(() => first.promise);

    const { result } = renderHook(() => useApi<SignalFeed>(URL, null, POLL_MS));

    first.reject(planRequired());
    await flush();
    expect(result.current.paywalled).toBe(true);

    // Customer upgrades — the next poll answers 200.
    const second = deferred<SignalFeed>();
    get.mockImplementationOnce(() => second.promise);
    await act(async () => {
      vi.advanceTimersByTime(POLL_MS);
    });
    expect(result.current.paywalled).toBe(true); // still held, mid-flight

    second.resolve({ signals: [{ id: "sig-1" }] });
    await flush();

    expect(result.current.paywalled).toBe(false);
    expect(result.current.paywallUrl).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.data).toEqual({ signals: [{ id: "sig-1" }] });
  });

  it("HOLDS the wall on a failure that is not a 402 — a blip is not evidence of payment", async () => {
    // Deliberate change of the earlier semantics. Clearing here would re-open
    // the same hole from a different trigger: a transient 500 on a 15s poll
    // would arm the one-click "Take trade" control for an unpaid customer.
    // A failed request says nothing about entitlement, so the last known state
    // stands until a SUCCESSFUL response replaces it. Failing closed costs a
    // paid customer one retry; failing open hands an unpaid customer a live
    // order control.
    const first = deferred<SignalFeed>();
    get.mockImplementationOnce(() => first.promise);

    const { result } = renderHook(() => useApi<SignalFeed>(URL, null, POLL_MS));
    first.reject(planRequired());
    await flush();
    expect(result.current.paywalled).toBe(true);

    // Next poll dies on a plain 500 — nothing to do with entitlement.
    const second = deferred<SignalFeed>();
    get.mockImplementationOnce(() => second.promise);
    await act(async () => {
      vi.advanceTimersByTime(POLL_MS);
    });
    second.reject(new ApiError(500, "server exploded"));
    await flush();

    expect(result.current.error).toBe("server exploded");
    expect(result.current.paywalled).toBe(true);
    expect(result.current.paywallUrl).toBe("/pricing?from=signals");
  });

  it("holds the error message across an in-flight refresh too", async () => {
    const first = deferred<SignalFeed>();
    get.mockImplementationOnce(() => first.promise);

    const { result } = renderHook(() => useApi<SignalFeed>(URL, null, POLL_MS));
    expect(result.current.error).toBeNull();

    first.reject(new ApiError(0, "Network error — is the backend running?"));
    await flush();
    expect(result.current.error).toBe("Network error — is the backend running?");

    const second = deferred<SignalFeed>();
    get.mockImplementationOnce(() => second.promise);
    await act(async () => {
      vi.advanceTimersByTime(POLL_MS);
    });

    // Same rule as the wall: the message stays until the new answer lands,
    // instead of vanishing for the length of every retry.
    expect(result.current.error).toBe("Network error — is the backend running?");

    second.resolve({ signals: [] });
    await flush();
    expect(result.current.error).toBeNull();
  });
});
