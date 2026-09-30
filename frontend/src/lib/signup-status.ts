/**
 * Is public signup open? (founder, 1 Oct 2026: "SIGNUP STAYS CLOSED to the public until the gate
 * is 8/8 … I do not want a stranger landing on a half-built journey.")
 *
 * THE SERVER IS THE GATE — POST /api/auth/register refuses any address that is not on the
 * server's allowlist, with its own Hinglish line. This file only stops the site from INVITING a
 * stranger to a form the server will refuse: every "Start Free" / "Account banao" link asks
 * `signupOpen()` and is hidden unless the backend says, live, `{"open": true}`.
 *
 * FAIL CLOSED: a 404 (an older backend without the endpoint), an error, a timeout or any body that
 * is not exactly `open: true` all mean CLOSED. A stranger may still type /register — the server
 * refuses him; an invited address still signs up there (the form stays, with a notice).
 */

import { api } from "@/shared/api/client";

export const SIGNUP_STATUS_PATH = "/auth/signup-status";
export const SIGNUP_STATUS_TIMEOUT_MS = 3000;
export const SIGNUP_STATUS_CACHE_MS = 60_000;

/** The one line shown wherever a signup link used to be (the server says the same in its 403). */
export const SIGNUP_CLOSED_LINE = "Abhi naye account band hain — jaldi khulenge.";
export const SIGNUP_INVITE_ONLY_LINE =
  "Abhi naye account sirf invite se bante hain. Invite wala email hi daaliye — baaki email par account nahi banega.";

export function isOpenBody(body: unknown): boolean {
  return typeof body === "object" && body !== null && (body as { open?: unknown }).open === true;
}

export async function fetchSignupOpen(timeoutMs: number = SIGNUP_STATUS_TIMEOUT_MS): Promise<boolean> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<boolean>((resolve) => {
    timer = setTimeout(() => resolve(false), timeoutMs);
  });
  const call = api.get<unknown>(SIGNUP_STATUS_PATH).then(isOpenBody, () => false);
  try {
    return await Promise.race([call, timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

let cache: { at: number; answer: Promise<boolean> } | null = null;

/** Cached for a minute so every link on a page asks the server once. */
export function signupOpen(timeoutMs?: number): Promise<boolean> {
  const now = Date.now();
  if (!cache || now - cache.at > SIGNUP_STATUS_CACHE_MS) {
    cache = { at: now, answer: fetchSignupOpen(timeoutMs) };
  }
  return cache.answer;
}

/** Test seam only. */
export function resetSignupStatusCache(): void {
  cache = null;
}
