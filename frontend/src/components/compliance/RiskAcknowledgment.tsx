/**
 * RiskAcknowledgment — required-checkbox component for the signup
 * form. Controlled component: parent owns the checked state and the
 * "show error" flag (set after a submit attempt while still
 * unchecked). The component stamps a timestamp into localStorage on
 * first-check so the audit trail survives form re-renders.
 */

"use client";

import Link from "next/link";

import {
  LS_KEY_RISK_ACK,
  RISK_ACK_COPY,
} from "@/lib/compliance/disclaimer-text";

export interface RiskAcknowledgmentProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  /** Render the inline error message when the user submits without
   *  checking. Parent flips this on the failed submit. */
  showError?: boolean;
  /** Defaults to "hi" so the signup form matches the rest of the
   *  app's default locale. */
  lang?: "en" | "hi";
}

function safeWrite(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* quota / private mode — silently drop */
  }
}

export function RiskAcknowledgment({
  checked,
  onChange,
  showError = false,
  lang = "hi",
}: RiskAcknowledgmentProps) {
  const copy = lang === "hi" ? RISK_ACK_COPY.hi : RISK_ACK_COPY.en;
  const errorCopy = lang === "hi" ? RISK_ACK_COPY.error_hi : RISK_ACK_COPY.error_en;

  return (
    <div
      data-testid="risk-acknowledgment"
      data-lang={lang}
      data-checked={checked ? "true" : "false"}
      className="space-y-1"
    >
      <label className="flex cursor-pointer items-start gap-2 text-xs leading-relaxed text-neutral-300">
        <input
          type="checkbox"
          checked={checked}
          data-testid="risk-ack-checkbox"
          aria-invalid={showError && !checked}
          aria-describedby={showError && !checked ? "risk-ack-error" : undefined}
          onChange={(e) => {
            const next = e.target.checked;
            onChange(next);
            if (next) {
              // Audit-trail timestamp persists even after the form
              // unmounts (e.g. successful submit redirect).
              safeWrite(LS_KEY_RISK_ACK, new Date().toISOString());
            }
          }}
          className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-white/20 bg-neutral-900 accent-emerald-500"
        />
        <span>
          {copy}{" "}
          <Link
            href="/compliance/legal"
            data-testid="risk-ack-link"
            className="text-emerald-400 underline-offset-2 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            ({lang === "hi" ? "padho" : "read"})
          </Link>
        </span>
      </label>
      {showError && !checked && (
        <p
          id="risk-ack-error"
          data-testid="risk-ack-error"
          role="alert"
          className="text-xs text-red-400"
        >
          {errorCopy}
        </p>
      )}
    </div>
  );
}
