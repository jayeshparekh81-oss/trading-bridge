"""AI signal validator — Claude as the AlgoMitra risk gate.

Every inbound :class:`StrategySignal` runs through :func:`validate_signal`
before the executor places orders. The validator returns an
:class:`AIDecision` (APPROVED / REJECTED + reasoning + confidence) which
the caller persists onto the signal row for audit.

The model is the existing ``algomitra_model`` setting (default
``claude-sonnet-4-6``). System prompt is marked cacheable so per-user
calls within a 5-minute window reuse the prefix and pay ~10% input
tokens for the bulk of the prompt.

Design choices:
    * **Structured output** — JSON schema enforced via ``output_config``
      so the response is parseable without prompt-engineering tricks.
    * **No streaming** — validation runs in the background task before
      execution; a 1-2 s synchronous round-trip is fine.
    * **Bypass switch** — if ``strategy.ai_validation_enabled`` is False
      the validator returns an APPROVED stub immediately. Useful for the
      Wed paper-mode test where we want to exercise the executor without
      burning Claude credits.
    * **Test seam** — the public :func:`validate_signal` accepts an
      optional ``client`` kwarg; tests inject a fake.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import anthropic

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.strategy_signal import StrategySignal
from app.schemas.ai_decision import AIDecision, AIDecisionStatus

_logger = get_logger("services.ai_validator")


SYSTEM_PROMPT = """\
You are AlgoMitra's risk validator for TRADETRI, an Indian retail algo \
trading platform. Your sole job is to APPROVE or REJECT inbound trading \
signals before any real order is placed.

You are deliberately conservative. When in doubt, REJECT. Capital \
preservation beats opportunity cost — the user can always re-enter on \
the next signal, but a bad fill in a hostile market is hard to recover.

═══════════════════════════════════════════════════════════════════════
WHAT YOU CHECK
═══════════════════════════════════════════════════════════════════════
1. **Direction conflict** — if the user already holds an open position \
   in the same symbol on the same side, REJECT (don't double-enter).
2. **Daily loss budget** — if today's realised loss is at or above the \
   strategy's max_loss_per_day, REJECT with reason "daily loss limit".
3. **Signal frequency** — if more than 6 signals in the last hour from \
   this strategy, REJECT as "spammy" (likely a chart bug).
4. **Market hours sanity** — if the signal is outside 09:15-15:25 IST \
   on a weekday, REJECT. The webhook layer also gates this; you are a \
   second line of defence.
5. **Symbol sanity** — empty / malformed symbol → REJECT.

═══════════════════════════════════════════════════════════════════════
OUTPUT
═══════════════════════════════════════════════════════════════════════
Respond ONLY with JSON matching the supplied schema:
    decision    — "APPROVED" or "REJECTED"
    reasoning   — one short sentence (max 200 chars), in plain English
    confidence  — 0.00 to 1.00 (how sure you are about this call)

Never wrap the JSON in prose. Never apologise. Never explain at length."""


_RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "ai_decision",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["decision", "reasoning", "confidence"],
        "properties": {
            "decision": {"type": "string", "enum": ["APPROVED", "REJECTED"]},
            "reasoning": {"type": "string", "maxLength": 200},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    },
}


class AIValidatorError(RuntimeError):
    """Wraps any anthropic SDK failure in the validator path."""


async def validate_signal(
    signal: StrategySignal,
    strategy: Strategy,
    *,
    recent_signal_count: int = 0,
    todays_loss_inr: int = 0,
    open_positions_summary: str = "(none)",
    client: anthropic.AsyncAnthropic | None = None,
) -> AIDecision:
    """Run the AI validation gate over an inbound signal.

    Returns:
        :class:`AIDecision` with decision, one-sentence reasoning, and a
        0-1 confidence. On a non-validating strategy or empty API key the
        function returns a synthetic ``APPROVED`` so the executor flows
        regardless — the caller is responsible for honouring the result.

    Raises:
        :class:`AIValidatorError` on SDK / parse failures. The caller
        should treat this as a soft "PENDING" — do NOT auto-execute on
        validator failure.
    """
    if not strategy.ai_validation_enabled:
        _logger.info(
            "ai_validator.bypass",
            signal_id=str(signal.id),
            reason="strategy.ai_validation_enabled=False",
        )
        return AIDecision(
            decision=AIDecisionStatus.APPROVED,
            reasoning="AI validation disabled for this strategy.",
            confidence=Decimal("1.000"),
        )

    settings = get_settings()
    api_key = settings.anthropic_api_key.get_secret_value()
    if not api_key:
        # Without a key we cannot validate; PAPER_MODE flag in the executor
        # is the user's safety net here. Emit a PENDING-style APPROVED with
        # explicit reasoning so the audit trail is honest.
        _logger.warning("ai_validator.no_api_key", signal_id=str(signal.id))
        return AIDecision(
            decision=AIDecisionStatus.APPROVED,
            reasoning="ANTHROPIC_API_KEY not configured; bypassing validator.",
            confidence=Decimal("0.000"),
        )

    user_message = _build_user_message(
        signal=signal,
        strategy=strategy,
        recent_signal_count=recent_signal_count,
        todays_loss_inr=todays_loss_inr,
        open_positions_summary=open_positions_summary,
    )

    sdk = client or anthropic.AsyncAnthropic(api_key=api_key)
    try:
        response = await sdk.messages.create(
            model=settings.algomitra_model,
            max_tokens=400,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": _RESPONSE_SCHEMA},
            },
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as exc:
        _logger.warning(
            "ai_validator.api_error",
            signal_id=str(signal.id),
            error_type=type(exc).__name__,
            message=str(exc),
        )
        raise AIValidatorError(f"Claude API error: {exc}") from exc

    return _parse_response(response, signal_id=str(signal.id))


def _build_user_message(
    *,
    signal: StrategySignal,
    strategy: Strategy,
    recent_signal_count: int,
    todays_loss_inr: int,
    open_positions_summary: str,
) -> str:
    """Assemble the per-call user message — keeps system prompt cacheable."""
    return (
        "SIGNAL\n"
        f"  Symbol     : {signal.symbol}\n"
        f"  Action     : {signal.action}\n"
        f"  Quantity   : {signal.quantity}\n"
        f"  OrderType  : {signal.order_type}\n"
        f"  ReceivedAt : {signal.received_at.isoformat()}\n"
        "\n"
        "STRATEGY\n"
        f"  Name        : {strategy.name}\n"
        f"  EntryLots   : {strategy.entry_lots}\n"
        f"  HardSLPct   : {strategy.hard_sl_pct or 'unset'}\n"
        f"  MaxLossDay  : {strategy.max_loss_per_day or 'unset'}\n"
        "\n"
        "RUNTIME CONTEXT\n"
        f"  TodaysLossINR     : {todays_loss_inr}\n"
        f"  SignalsLastHour   : {recent_signal_count}\n"
        f"  OpenPositions     : {open_positions_summary}\n"
        "\n"
        "Decide. JSON only."
    )


def _parse_response(response: Any, *, signal_id: str) -> AIDecision:
    """Extract the JSON payload from the Claude response."""
    text_block = next(
        (b for b in response.content if getattr(b, "type", None) == "text"),
        None,
    )
    if text_block is None:
        raise AIValidatorError("No text block in Claude response")

    try:
        payload = json.loads(text_block.text)
    except json.JSONDecodeError as exc:
        raise AIValidatorError(
            f"Claude returned non-JSON despite schema: {text_block.text[:200]}"
        ) from exc

    try:
        decision = AIDecisionStatus(payload["decision"])
        reasoning = str(payload["reasoning"])
        confidence = Decimal(str(payload["confidence"]))
    except (KeyError, ValueError) as exc:
        raise AIValidatorError(
            f"Claude payload missing fields or bad types: {payload}"
        ) from exc

    _logger.info(
        "ai_validator.decision",
        signal_id=signal_id,
        decision=decision.value,
        confidence=str(confidence),
    )
    return AIDecision(
        decision=decision,
        reasoning=reasoning,
        confidence=confidence,
    )


__all__ = ["AIValidatorError", "validate_signal"]
