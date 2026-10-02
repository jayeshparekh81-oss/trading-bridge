"use client";

/**
 * ReturnPathProbe — the ONE place /login and /register read `?next=`.
 *
 * WHY THIS EXISTS (found 2 Oct 2026, the StrykeX Stage-1 audit, measured on the served site):
 * `useSearchParams()` makes Next bail out of static rendering up to the nearest <Suspense>.
 * Both auth pages wrapped their WHOLE page in `<Suspense fallback={null}>`, so the server HTML
 * of /login and /register was an empty shell — only the footer disclaimer — and a customer on
 * a phone saw a BLANK screen until ~285 KB (gzip) of JavaScript had downloaded and run
 * (served build 67a3e41e: `<template data-dgst="BAILOUT_TO_CLIENT_SIDE_RENDERING">`).
 *
 * Now only this probe bails out (it renders nothing), and the page around it — the title,
 * the form, the way back — is in the server HTML from the first byte. The probe hands the
 * sanitised path up through a callback; the page keeps it in state and uses it exactly as
 * before (login/register(…, nextPath) and the "/register?next=…" link).
 *
 * Guard: tests/auth/ssr-first-paint.test.tsx — the two pages may not wrap themselves in a
 * Suspense boundary and may not call useSearchParams themselves.
 */

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

import { safeNextPath } from "@/lib/safe-next";

export function ReturnPathProbe({ onPath }: { onPath: (path: string) => void }) {
  const next = safeNextPath(useSearchParams().get("next"));
  useEffect(() => {
    onPath(next);
  }, [next, onPath]);
  return null;
}
