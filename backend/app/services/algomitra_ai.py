"""AlgoMitra AI service — Claude-powered chat companion.

Phase 1B replaces the static FAQ/flow chat with real Claude calls. The
SDK is the official ``anthropic`` Python client; the model defaults to
``claude-sonnet-4-6`` (overridable via :class:`Settings.algomitra_model`).

Design choices (all confirmed with founder):
    * **Crisp output** — `max_tokens=600`, structured JSON output,
      explicit length budget in the system prompt. Veteran tone, never
      dumps an essay.
    * **Anticipated questions as JSON suggestions** — the model returns
      a strict schema so the frontend can render chips deterministically.
    * **Prompt caching** — the system prompt is the prefix; we mark it
      ``ephemeral`` so repeat callers within ~5 minutes get ~90% off
      input tokens. Per-user / per-turn data lives in ``messages``,
      never in the system prompt (that would invalidate the cache).
    * **Adaptive thinking, effort=low** — Claude decides if a tiny
      thinking step helps (e.g., math, scheduling), but stays cheap.
    * **No streaming yet** — Phase 1C may add SSE; for 100-150 word
      responses the latency is already <2s.
    * **Fallback** — if the API errors, the caller (`api/algomitra.py`)
      catches and returns a degraded response so the frontend can fall
      back to the static flow library without breaking the chat.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import anthropic

from app.core.config import get_settings
from app.core.logging import get_logger

_logger = get_logger("services.algomitra_ai")


# ═══════════════════════════════════════════════════════════════════════
# System prompt — the persona, rules, escalation triggers, restrictions
# ═══════════════════════════════════════════════════════════════════════

#: AlgoMitra system prompt. Stable across all requests so it caches well.
#: Sized to clear Sonnet 4.6's 2048-token cache-prefix minimum (~2.5K
#: tokens with the BCP). Edit only when the persona itself changes —
#: per-user / per-turn context goes into ``messages``, never here.
SYSTEM_PROMPT = """\
You are AlgoMitra (आल्गो मित्र), TRADETRI's AI trading companion. \
TRADETRI is an Indian platform that bridges TradingView signals to \
broker APIs (Fyers, Dhan; Zerodha/Upstox/AngelOne in roadmap). The \
founder is Jayesh Parekh — ex-L&T, 24 years in tech, based in Vadodara.

═══════════════════════════════════════════════════════════════════════
PERSONA — 15 years of compounded experience across 4 areas
═══════════════════════════════════════════════════════════════════════
1. Hospitality (Taj Hotels-level service): warm, never condescending.
2. IT mentorship: senior architect, knows when to teach vs. just fix.
3. Trading (NSE/BSE since 2010): F&O, options, indices, equity, MCX.
4. Trading psychology: behavioural finance, biases, emotional safety.

You sound like a chai-side senior brother — supportive, direct, never \
preachy. You mix Hindi-English (Hinglish) naturally, but at most 1-2 \
"bhai" or Hinglish phrases per response. Don't force it.

═══════════════════════════════════════════════════════════════════════
RESPONSE RULES — CRITICAL, NON-NEGOTIABLE
═══════════════════════════════════════════════════════════════════════
1. CRISP. 100-150 words MAX. NO LONG LECTURES. EVER.
2. Anticipate the user's likely next 2-4 questions. Return them as \
   the `suggestions` array — do NOT dump everything inline.
3. Bullet points / short lines, not paragraphs. Use structure.
4. End with an open hook ("Aage kya jaanna hai?" / "Aur details?") \
   only when suggestions are non-empty.
5. Use Hinglish 1-2 times max — "bhai", "samjha", "yaad rakh".
6. Numbers in INR (₹). Avoid USD unless explicitly relevant.
7. Veteran tone: pause, redirect, give the *one* useful thing — \
   not the textbook.
8. NEVER respond with more than 600 output tokens. The schema enforces \
   length implicitly; respect it.

GOOD example (Iron Condor):
   "4-leg options strategy. Range-bound markets best.
    Beginner-friendly. Win rate 70-80%, capital ₹40K+ chahiye.

    Aage kya jaanna hai?"
   suggestions: ["Setup karo", "Live example", "Risk samjhao"]

BAD: 500-word essay. Don't do this. Ever.

═══════════════════════════════════════════════════════════════════════
KNOWLEDGE BASE
═══════════════════════════════════════════════════════════════════════
TRADETRI tiers:
   • Tier 1 — Free (basic webhook → broker bridge)
   • Tier 2 — ₹999/mo (kill switch, multi-strategy, paper mode)
   • Tier 3 — coming soon (copy trading, advanced analytics)

Brokers (live):
   • Fyers — App ID + App Secret. OAuth flow.
   • Dhan — Client ID + Personal Access Token. Token expires; regenerate.
   Zerodha/Upstox/AngelOne/Shoonya — roadmap.

Indian markets:
   • Equity: 9:15-15:30 IST. Pre-open 9:00-9:08.
   • F&O: same window. NIFTY/BANKNIFTY/FINNIFTY/MIDCPNIFTY weekly \
     expiries (rotating Tue-Fri). Stocks monthly (last Thursday).
   • MCX: 9:00-23:30 IST. T+1 settlement on equity.

Strategies you can explain crisply:
   • Iron Condor, Butterfly, Straddle, Strangle (options)
   • Bull/Bear spreads (call/put)
   • Momentum, Mean reversion, Breakout (directional)
   • Scalping, Swing, Positional (timeframes)

Risk management commandments:
   1. Per-trade risk ≤ 1-2% of capital.
   2. Daily loss limit ≤ 5% of capital (kill switch enforces).
   3. Stop loss pre-defined BEFORE entry. Always.
   4. Position size = (Capital × Risk%) / (Entry − SL).
   5. After loss day, next day half-size only.

7 trading psychology biases:
   FOMO • Greed • Revenge trading • Fear • Overconfidence • \
   Paralysis • Tilt.

═══════════════════════════════════════════════════════════════════════
ESCALATION TRIGGERS
═══════════════════════════════════════════════════════════════════════
Suggest WhatsApp/Calendly handoff when:
   • Loss > ₹50,000 in a day or week
   • Severe emotional distress (more than the conversational down-day)
   • User explicitly asks for buy/sell calls
   • Complex tax / legal / compliance questions
   • Technical issue not resolved after 1-2 back-and-forth turns

Phrase it like: "Bhai, isme founder Jayesh se direct baat better hai. \
WhatsApp karo." Then put 'WhatsApp founder' or 'Book Calendly' in suggestions.

CRISIS mode (suicidal ideation, severe depression, self-harm hints):
   • Mental health > money. ALWAYS.
   • Mention iCall: 9152987821 (free, confidential, 8am-10pm IST).
   • Suggest immediate human contact (founder + iCall both).
   • Use `tone: "crisis"` in your response.

═══════════════════════════════════════════════════════════════════════
STRICT RESTRICTIONS — NEVER VIOLATE
═══════════════════════════════════════════════════════════════════════
1. NO specific buy/sell calls. Ever. Not even "thoda RELIANCE le lo". \
   If asked, deflect: "Specific calls SEBI-regulated hain. \
   Strategy frameworks bata sakta hoon, individual recommendations nahi."
2. NO market predictions ("NIFTY ye kal X hoga"). Probabilistic / \
   conditional language only.
3. NO guaranteed-return claims. EVER. "Backtest mein 70% win rate hai" — OK. \
   "Tu paisa banayega" — NOT OK.
4. ALWAYS mention risk when discussing strategies. One line minimum.
5. Mental health > money. Capital can be rebuilt; the trader cannot.
6. Don't invent TRADETRI features that don't exist. If uncertain, say \
   "Founder se confirm kar lo."
7. Indian context default (₹, IST, NSE/BSE). Adjust if user explicitly \
   asks about US/UK markets.

═══════════════════════════════════════════════════════════════════════
OUTPUT SCHEMA — STRICT JSON, ENFORCED
═══════════════════════════════════════════════════════════════════════
You MUST return JSON matching this shape:
{
  "message": string,           // The crisp 100-150 word reply (Hinglish OK).
  "suggestions": string[],     // 0-4 anticipated next-question chips, ≤25 chars each.
  "tone": "normal" | "empathy" | "celebration" | "warning" | "crisis"
}

`tone` guides the frontend's visual treatment:
   • normal — default chat bubble
   • empathy — soft tone (loss day, frustration)
   • celebration — positive (wins, milestones)
   • warning — flagged behaviour (revenge trading, overleveraging)
   • crisis — mental health emergency, surface iCall + founder immediately

Suggestions should be IMPERATIVE labels: "Show example", "Setup karo", \
"Risk samjhao". Not full sentences. Empty array is fine if the answer \
is fully self-contained.
"""


# ═══════════════════════════════════════════════════════════════════════
# JSON schema for structured outputs
# ═══════════════════════════════════════════════════════════════════════

#: Strict JSON schema enforced via ``output_config.format``. Keep
#: deterministic — adding/removing fields invalidates Claude's compiled
#: schema cache (24h TTL on the API side).
_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "tone": {
            "type": "string",
            "enum": ["normal", "empathy", "celebration", "warning", "crisis"],
        },
    },
    "required": ["message", "suggestions", "tone"],
    "additionalProperties": False,
}


# ═══════════════════════════════════════════════════════════════════════
# Pricing — Sonnet 4.6 ($3 input / $15 output per 1M, cache reads ~10%)
# ═══════════════════════════════════════════════════════════════════════

# USD per million tokens. Update if model changes.
_USD_PER_1M_INPUT = 3.0
_USD_PER_1M_OUTPUT = 15.0
_CACHE_READ_DISCOUNT = 0.10   # cache reads cost ~0.1× base
_CACHE_WRITE_PREMIUM = 1.25   # cache writes cost ~1.25× base


# ═══════════════════════════════════════════════════════════════════════
# Public dataclass
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ChatResult:
    """Outcome of one ``AlgoMitraAI.chat()`` call."""

    message: str
    suggestions: tuple[str, ...]
    tone: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cost_inr: Decimal
    raw_stop_reason: str


# ═══════════════════════════════════════════════════════════════════════
# Service
# ═══════════════════════════════════════════════════════════════════════


class AlgoMitraAIError(Exception):
    """Wrapper for any failure inside the AI service.

    The API layer catches this and returns a graceful 503 so the
    frontend can fall back to static flows without breaking the UX.
    """


class AlgoMitraAI:
    """Thin wrapper around :class:`anthropic.AsyncAnthropic`."""

    def __init__(self, *, client: anthropic.AsyncAnthropic | None = None) -> None:
        settings = get_settings()
        api_key = settings.anthropic_api_key.get_secret_value()
        if not api_key:
            raise AlgoMitraAIError(
                "ANTHROPIC_API_KEY not set; AlgoMitra AI disabled."
            )
        self._client = client or anthropic.AsyncAnthropic(api_key=api_key)
        self._model = settings.algomitra_model
        self._usd_to_inr = settings.algomitra_usd_to_inr

    async def chat(
        self,
        *,
        user_message: str,
        history: list[dict[str, str]],
        user_context: dict[str, Any] | None = None,
    ) -> ChatResult:
        """Send one user turn to Claude and return the parsed result.

        Args:
            user_message: The current free-text from the user.
            history: Last N messages as ``[{"role": "...", "content": "..."}]``.
                Caller is responsible for trimming + ordering (oldest → newest).
            user_context: Privacy-safe dict (name, broker_count, etc.). Injected
                as a synthetic first turn so the system prompt stays cacheable.

        Raises:
            AlgoMitraAIError: any SDK failure, with the original exception
                as ``__cause__``.
        """
        messages = self._build_messages(user_message, history, user_context)
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=600,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": _RESPONSE_SCHEMA},
                },
                messages=messages,
            )
        except anthropic.APIError as exc:
            _logger.warning(
                "algomitra.api_error",
                error_type=type(exc).__name__,
                status=getattr(exc, "status_code", None),
                message=str(exc),
            )
            raise AlgoMitraAIError(f"Claude API error: {exc}") from exc
        except Exception as exc:  # pragma: no cover — defensive
            _logger.exception("algomitra.unexpected_error")
            raise AlgoMitraAIError("AlgoMitra AI failed") from exc

        return self._parse_response(response)

    # ──────────────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_messages(
        user_message: str,
        history: list[dict[str, str]],
        user_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Assemble the messages array, injecting context as a synthetic turn.

        Context goes into the user-message stream (not the system prompt) so
        that the system prompt can be cached across all users — see the
        prompt-caching guidance in the Anthropic skill.
        """
        msgs: list[dict[str, Any]] = []
        if user_context:
            ctx_text = _format_user_context(user_context)
            msgs.append({"role": "user", "content": ctx_text})
            msgs.append(
                {
                    "role": "assistant",
                    "content": "Samjha bhai. Bata, kya help chahiye?",
                }
            )
        for h in history:
            role = h.get("role")
            content = h.get("content", "")
            if role in ("user", "assistant") and content:
                msgs.append({"role": role, "content": content})
        msgs.append({"role": "user", "content": user_message})
        return msgs

    def _parse_response(self, response: Any) -> ChatResult:
        """Pull the JSON payload + usage stats out of the SDK response."""
        text_block = next(
            (b for b in response.content if getattr(b, "type", None) == "text"),
            None,
        )
        if text_block is None:
            raise AlgoMitraAIError("No text block in Claude response")
        try:
            payload = json.loads(text_block.text)
        except json.JSONDecodeError as exc:
            raise AlgoMitraAIError(
                f"Claude returned non-JSON despite schema: {text_block.text[:200]}"
            ) from exc

        message = str(payload.get("message", "")).strip()
        suggestions_raw = payload.get("suggestions", [])
        if not isinstance(suggestions_raw, list):
            suggestions_raw = []
        suggestions = tuple(str(s).strip() for s in suggestions_raw if str(s).strip())[:4]
        tone = str(payload.get("tone", "normal"))
        if tone not in ("normal", "empathy", "celebration", "warning", "crisis"):
            tone = "normal"

        usage = response.usage
        input_tokens = int(getattr(usage, "input_tokens", 0))
        output_tokens = int(getattr(usage, "output_tokens", 0))
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cache_creation = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)

        cost_inr = self._compute_cost_inr(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read=cache_read,
            cache_creation=cache_creation,
        )

        return ChatResult(
            message=message,
            suggestions=suggestions,
            tone=tone,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
            cost_inr=cost_inr,
            raw_stop_reason=str(getattr(response, "stop_reason", "")),
        )

    def _compute_cost_inr(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_read: int,
        cache_creation: int,
    ) -> Decimal:
        """Compute INR cost with cache discount + write premium accounted for."""
        # input_tokens is the *uncached* input only on the response.usage object.
        # Cache reads and writes are reported separately.
        usd = (
            input_tokens * (_USD_PER_1M_INPUT / 1_000_000)
            + cache_read * (_USD_PER_1M_INPUT * _CACHE_READ_DISCOUNT / 1_000_000)
            + cache_creation * (_USD_PER_1M_INPUT * _CACHE_WRITE_PREMIUM / 1_000_000)
            + output_tokens * (_USD_PER_1M_OUTPUT / 1_000_000)
        )
        return Decimal(str(round(usd * self._usd_to_inr, 4)))


def _format_user_context(ctx: dict[str, Any]) -> str:
    """Render the context dict as a short Hinglish preamble."""
    parts = ["Mere baare mein context (chat ke pehle):"]
    if name := ctx.get("name"):
        parts.append(f"• Naam: {name}")
    if (bc := ctx.get("broker_count")) is not None:
        parts.append(f"• Connected brokers: {bc}")
    if (tc := ctx.get("trade_count")) is not None:
        parts.append(f"• Total trades so far: {tc}")
    if (pnl := ctx.get("today_pnl")) is not None:
        parts.append(f"• Today's P&L: ₹{pnl}")
    if page := ctx.get("current_page"):
        parts.append(f"• Currently on page: {page}")
    parts.append("\nAb mera sawaal:")
    return "\n".join(parts)


__all__ = ["AlgoMitraAI", "AlgoMitraAIError", "ChatResult", "SYSTEM_PROMPT"]
