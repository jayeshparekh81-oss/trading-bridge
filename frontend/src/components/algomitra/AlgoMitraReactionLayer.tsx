"use client";

import { useAlgoMitraLive } from "@/hooks/useAlgoMitraLive";
import { ReactionToast } from "./ReactionToast";

/**
 * Single-mount layer for the AlgoMitra Live Reaction system.
 *
 * Owns the polling hook so all dashboard pages share one poller —
 * placed in ``(dashboard)/layout.tsx`` next to the ``ChatWidget``.
 * Renders only the reaction toast; the chat widget stays separate
 * so the two systems can fail independently.
 */
export function AlgoMitraReactionLayer() {
  const { message, dismiss } = useAlgoMitraLive();
  return <ReactionToast message={message} onDismiss={dismiss} />;
}
