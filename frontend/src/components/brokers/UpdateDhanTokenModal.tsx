"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ExternalLink, Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { GlowButton } from "@/components/ui/glow-button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";

//: Backend ``UpdateDhanTokenRequest`` rejects shorter input with 422;
//: surface the same floor in the UI so the user gets immediate
//: feedback before paying the round-trip.
const MIN_TOKEN_LENGTH = 100;

//: Default label that matches the backend default when the user
//: doesn't customise it. Keeps the success message wording stable.
const DEFAULT_LABEL = "Dhan – Primary";

//: Auto-close delay after success — short enough to feel snappy,
//: long enough that the user reads the confirmation.
const SUCCESS_AUTOCLOSE_MS = 2000;

//: Deep link to the Dhan API access page. Stable URL from Dhan web app.
const DHAN_API_ACCESS_URL = "https://web.dhan.co/api-access";

type Stage = "idle" | "submitting" | "success" | "error";

export type UpdateDhanTokenModalProps = {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  /**
   * Optional Dhan client ID — when omitted, the backend reuses the
   * client ID from the user's most recent Dhan credential. First-time
   * users must supply it via the input field rendered inside the
   * modal.
   */
  initialClientId?: string;
};

/**
 * "Update Dhan Token" modal.
 *
 * Flow:
 *   1. User opens Dhan dashboard via the external-link button.
 *   2. User generates a fresh 24h PAT in Dhan.
 *   3. User pastes the token here + optional client ID.
 *   4. We POST to ``/api/brokers/dhan/update-token`` — the backend
 *      validates the token against Dhan, encrypts it, persists, and
 *      busts the per-user session cache so chart + backtest + paper
 *      trading start using the new token immediately.
 *   5. Success → green confirmation → auto-close after 2s → caller's
 *      ``onSuccess`` callback (typically refetches the status badge).
 *
 * The component is purely additive — it does not alter the rest of
 * the brokers page or the existing Fyers OAuth path.
 */
export function UpdateDhanTokenModal({
  open,
  onClose,
  onSuccess,
  initialClientId,
}: UpdateDhanTokenModalProps) {
  const [token, setToken] = useState<string>("");
  const [clientId, setClientId] = useState<string>(initialClientId ?? "");
  const [label, setLabel] = useState<string>(DEFAULT_LABEL);
  const [stage, setStage] = useState<Stage>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");

  // Tracks the auto-close timer so we can cancel it if the user closes
  // the modal manually during the success-confirmation window.
  const successTimerRef = useRef<number | null>(null);

  // Reset the form whenever the modal opens (so a previous error /
  // success doesn't bleed into the next session) and clear any
  // pending success-timer on unmount. The setState calls inside the
  // effect intentionally cascade — they fire once per open transition
  // and React 19 batches the resulting re-render. The lint rule
  // ``react-hooks/set-state-in-effect`` would have us hoist this into
  // a ``key`` prop driven by ``open``; the Dialog primitive doesn't
  // remount its children on open-toggle, so the only reliable reset
  // hook is this effect.
  useEffect(() => {
    if (open) {
      /* eslint-disable react-hooks/set-state-in-effect */
      setToken("");
      setClientId(initialClientId ?? "");
      setLabel(DEFAULT_LABEL);
      setStage("idle");
      setErrorMessage("");
      /* eslint-enable react-hooks/set-state-in-effect */
    }
    return () => {
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
        successTimerRef.current = null;
      }
    };
  }, [open, initialClientId]);

  const trimmedToken = token.trim();
  const trimmedClientId = clientId.trim();
  const tokenLengthOk = trimmedToken.length >= MIN_TOKEN_LENGTH;
  const submitDisabled =
    stage === "submitting" || stage === "success" || !tokenLengthOk;

  async function handleSubmit(): Promise<void> {
    if (submitDisabled) return;
    setStage("submitting");
    setErrorMessage("");

    type Response = {
      success: boolean;
      connection_status: string;
      message: string;
      token_label: string;
      updated_at: string;
    };

    try {
      await api.post<Response>("/brokers/dhan/update-token", {
        access_token: trimmedToken,
        // Send dhan_client_id only when the user provided a non-empty
        // value; omission triggers the backend "inherit from existing"
        // path for token-only rotations.
        ...(trimmedClientId ? { dhan_client_id: trimmedClientId } : {}),
        label: label.trim() || DEFAULT_LABEL,
      });
      setStage("success");
      successTimerRef.current = window.setTimeout(() => {
        successTimerRef.current = null;
        onSuccess();
        onClose();
      }, SUCCESS_AUTOCLOSE_MS);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.detail
          : "Couldn't update Dhan token. Try again.";
      setErrorMessage(message);
      setStage("error");
    }
  }

  function handleOpenChange(next: boolean): void {
    // Block close while a request is in flight — preserves UX
    // expectations and avoids a partial state in the network log.
    if (stage === "submitting") return;
    if (!next) onClose();
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update Dhan Access Token</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 pt-2" data-testid="update-dhan-token-modal">
          {/* Instructions */}
          <div
            className="space-y-2 rounded-lg border border-border bg-muted/30 p-3 text-sm"
            data-testid="dhan-token-instructions"
          >
            <p className="font-medium">How to generate a fresh token:</p>
            <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
              <li>
                Open Dhan web →{" "}
                <a
                  href={DHAN_API_ACCESS_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-accent-blue underline-offset-2 hover:underline"
                  data-testid="dhan-api-access-link"
                >
                  Profile → API Access
                  <ExternalLink className="h-3 w-3" aria-hidden />
                </a>
              </li>
              <li>Click <span className="font-medium">Generate New Token</span> (valid for 24 hours)</li>
              <li>Copy the token and paste it below</li>
            </ol>
          </div>

          {/* Token textarea */}
          <div>
            <label
              htmlFor="dhan-access-token"
              className="text-sm font-medium"
            >
              Dhan Access Token
            </label>
            <textarea
              id="dhan-access-token"
              data-testid="dhan-token-input"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste your Dhan access token here..."
              rows={4}
              spellCheck={false}
              autoComplete="off"
              autoCorrect="off"
              className="mt-1 w-full rounded-lg border border-input bg-transparent px-3 py-2 font-mono text-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
              disabled={stage === "submitting" || stage === "success"}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Minimum {MIN_TOKEN_LENGTH} characters — Dhan tokens are JWTs around 300+ chars.
            </p>
          </div>

          {/* Optional Client ID */}
          <div>
            <label htmlFor="dhan-client-id" className="text-sm font-medium">
              Client ID{" "}
              <span className="text-xs text-muted-foreground">(optional after first connect)</span>
            </label>
            <Input
              id="dhan-client-id"
              data-testid="dhan-client-id-input"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="e.g., 1100123456"
              className="mt-1"
              disabled={stage === "submitting" || stage === "success"}
            />
          </div>

          {/* Optional Label */}
          <div>
            <label htmlFor="dhan-label" className="text-sm font-medium">
              Label
            </label>
            <Input
              id="dhan-label"
              data-testid="dhan-label-input"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder={DEFAULT_LABEL}
              className="mt-1"
              disabled={stage === "submitting" || stage === "success"}
            />
          </div>

          {/* Error banner */}
          {stage === "error" && errorMessage && (
            <div
              role="alert"
              data-testid="dhan-token-error"
              className="rounded-lg border border-loss/30 bg-loss/5 px-3 py-2 text-sm text-loss"
            >
              {errorMessage}
            </div>
          )}

          {/* Success banner */}
          {stage === "success" && (
            <div
              role="status"
              data-testid="dhan-token-success"
              className="flex items-center gap-2 rounded-lg border border-profit/30 bg-profit/5 px-3 py-2 text-sm text-profit"
            >
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>
                Connected! Chart, backtest, and paper trading are now live.
              </span>
            </div>
          )}

          {/* Footer actions */}
          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={stage === "submitting"}
              className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="dhan-token-cancel"
            >
              Cancel
            </button>
            <GlowButton
              size="sm"
              onClick={handleSubmit}
              disabled={submitDisabled}
              data-testid="dhan-token-submit"
            >
              {stage === "submitting" ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Validating with Dhan...
                </span>
              ) : stage === "success" ? (
                "Connected"
              ) : (
                "Validate & Save"
              )}
            </GlowButton>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
