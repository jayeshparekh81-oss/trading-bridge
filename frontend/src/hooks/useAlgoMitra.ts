"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { findBestFaq, getFaqAnswer } from "@/lib/algomitra-faqs";
import {
  FLOWS,
  type Flow,
  type FlowId,
  type FlowOption,
  type FlowStep,
} from "@/lib/algomitra-flows";
import {
  ALGOMITRA_ESCALATION,
  FALLBACK_MESSAGES,
  FRIENDLY_INTENT_LABELS,
  IMAGE_ACK_MESSAGES,
  OPENING_QUESTIONS,
  detectEmotionalDistress,
  detectIntents,
  timeGreeting,
  type Intent,
} from "@/lib/algomitra-personality";
import { detectLanguage, type Language } from "@/lib/language-detector";

// ─── Types ──────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  imageDataUrl?: string;
  options?: readonly FlowOption[];
  flowId?: FlowId;
  flowStep?: string;
}

interface FlowState {
  flowId: FlowId;
  stepId: string;
}

// ─── Constants ──────────────────────────────────────────────────────────

const SESSION_KEY = "tb_algomitra_session";
const UNREAD_KEY = "tb_algomitra_unread";
const SEEN_INTRO_KEY = "tb_algomitra_seen_intro";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function readSession(): string {
  if (typeof window === "undefined") return newId();
  const existing = sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const id = newId();
  sessionStorage.setItem(SESSION_KEY, id);
  return id;
}

// ─── Intent chip builder ────────────────────────────────────────────────

/**
 * Build the universal intent chip set, with detected intents promoted to
 * the front. The chips route into existing flows so we don't create
 * orphaned dead-ends. The "Specific Question" chip closes the current
 * flow and prompts the user to type — it stays last.
 */
function intentChips(detected: Intent[], compact = false): readonly FlowOption[] {
  const all: Record<Intent, FlowOption> = {
    beginner: {
      label: "Beginner Guide",
      emoji: "🌱",
      action: { kind: "switch_flow", flowId: "welcome", nextStep: "newbie" },
    },
    strategy: {
      label: "Strategy Help",
      emoji: "🎯",
      action: { kind: "switch_flow", flowId: "education", nextStep: "topic" },
    },
    risk: {
      label: "Risk Management",
      emoji: "🛡️",
      action: { kind: "switch_flow", flowId: "education", nextStep: "risk" },
    },
    setup: {
      label: "Platform Setup",
      emoji: "🔌",
      action: { kind: "switch_flow", flowId: "setup" },
    },
    specific: {
      label: "Specific Question",
      emoji: "✏️",
      action: { kind: "next", nextStep: "__ask_for_question__" },
    },
  };
  // Promote detected intents to the front; keep the rest in canonical order.
  const order: Intent[] = ["beginner", "strategy", "risk", "setup"];
  const promoted = detected.filter((i) => order.includes(i));
  const rest = order.filter((i) => !promoted.includes(i));
  const final = [...promoted, ...rest, "specific" as Intent];
  return compact ? final.slice(0, 3).map((i) => all[i]) : final.map((i) => all[i]);
}

/** Conjunction word ("X and Y") in each free-tier language. */
const AND_WORD: Record<Language, string> = {
  hinglish: "aur",
  en: "and",
  hi: "और",
  gu: "અને",
};

/** Generic "trading" fallback when no specific intent was detected. */
const TRADING_FALLBACK: Record<Language, string> = {
  hinglish: "trading",
  en: "trading",
  hi: "trading",
  gu: "trading",
};

function friendlyIntentList(intents: Intent[], lang: Language): string {
  const labels = FRIENDLY_INTENT_LABELS[lang];
  const named = intents
    .filter((i): i is Exclude<Intent, "specific"> => i !== "specific")
    .map((i) => labels[i]);
  if (named.length === 0) return TRADING_FALLBACK[lang];
  if (named.length === 1) return named[0];
  return `${named.slice(0, -1).join(", ")} ${AND_WORD[lang]} ${named.at(-1)}`;
}

// ─── Backend AI call (Phase 1B — Claude) ────────────────────────────────

interface AIChatResponse {
  message: string;
  suggestions: string[];
  tone: "normal" | "empathy" | "celebration" | "warning" | "crisis";
  user_message_id: string;
  assistant_message_id: string;
  usage: {
    input_tokens: number;
    output_tokens: number;
    cache_read_tokens: number;
    cache_creation_tokens: number;
    cost_inr: string;
    daily_used: number;
    daily_limit: number;
    daily_remaining: number;
  };
}

/**
 * POST a free-text user turn to the AI endpoint and return the parsed
 * response. Re-throws ApiError so the caller can branch on status (429
 * = rate-limited, 503 = AI degraded → static-flow fallback).
 */
async function sendToAI(
  sessionId: string,
  message: string,
  hasImage: boolean,
): Promise<AIChatResponse> {
  const currentPage =
    typeof window !== "undefined" ? window.location.pathname : null;
  return await api.post<AIChatResponse>("/algomitra/messages", {
    session_id: sessionId,
    message,
    current_page: currentPage,
    has_image: hasImage,
  });
}

/** Map Claude's plain-string suggestions to clickable chips. */
function suggestionsToOptions(suggestions: string[]): readonly FlowOption[] {
  return suggestions.slice(0, 4).map((label) => ({
    label,
    action: { kind: "chat_send", text: label } as const,
  }));
}

// ─── Hook ───────────────────────────────────────────────────────────────

export interface UseAlgoMitra {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
  reset: () => void;
  unreadCount: number;
  messages: ChatMessage[];
  /** Currently active flow step's quick options, if any. */
  activeOptions: readonly FlowOption[] | undefined;
  /** True while the Claude API call is in flight — show the typing indicator. */
  isThinking: boolean;
  sendUserText: (text: string) => void;
  sendUserImage: (dataUrl: string, fileName: string) => void;
  selectOption: (option: FlowOption) => void;
}

export function useAlgoMitra(): UseAlgoMitra {
  const { user } = useAuth();
  const router = useRouter();

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [flowState, setFlowState] = useState<FlowState | null>(null);
  const [isThinking, setIsThinking] = useState(false);

  const sessionIdRef = useRef<string>("");
  const hasSeededRef = useRef(false);
  const hasIntroducedRef = useRef(false);
  /** Most recently detected user language — used for image acks etc. */
  const lastLangRef = useRef<Language>("hinglish");

  // Lazy-init session id + restore unread count from sessionStorage. This
  // effect *is* the canonical "sync once from an external store on mount"
  // pattern; the alternative (useSyncExternalStore) is overkill for a
  // one-shot read.
  useEffect(() => {
    sessionIdRef.current = readSession();
    if (typeof window === "undefined") return;
    const stored = sessionStorage.getItem(UNREAD_KEY);
    if (!stored) return;
    const n = Math.max(0, parseInt(stored, 10) || 0);
    if (n > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot mount restore from sessionStorage
      setUnreadCount(n);
    }
  }, []);

  // Persist unread count across reloads of the same browser session.
  useEffect(() => {
    if (typeof window === "undefined") return;
    sessionStorage.setItem(UNREAD_KEY, String(unreadCount));
  }, [unreadCount]);

  // Push an assistant message + (optionally) advance flow state.
  const pushAssistant = useCallback(
    (step: FlowStep, flowId: FlowId) => {
      const userName = user?.full_name?.split(" ")[0] || user?.email?.split("@")[0] || "bhai";
      const content = step.message.replace(/\{userName\}/g, userName);
      const msg: ChatMessage = {
        id: newId(),
        role: "assistant",
        content,
        timestamp: Date.now(),
        options: step.options,
        flowId,
        flowStep: step.id,
      };
      setMessages((prev) => [...prev, msg]);
      setFlowState({ flowId, stepId: step.id });
    },
    [user],
  );

  const pushUser = useCallback((content: string, imageDataUrl?: string) => {
    const msg: ChatMessage = {
      id: newId(),
      role: "user",
      content,
      timestamp: Date.now(),
      imageDataUrl,
    };
    setMessages((prev) => [...prev, msg]);
  }, []);

  // Seed the welcome flow with greeting + first step. Called from open()
  // and reset() — kept out of useEffect so React's strict cascading-render
  // rule stays satisfied.
  const seedWelcome = useCallback(() => {
    if (hasSeededRef.current) return;
    hasSeededRef.current = true;
    const welcome = FLOWS.welcome;
    const lang = lastLangRef.current;
    const userName =
      user?.full_name?.split(" ")[0] ||
      user?.email?.split("@")[0] ||
      "bhai";
    const isReturning =
      typeof window !== "undefined" &&
      localStorage.getItem(SEEN_INTRO_KEY) !== null;
    const greeting = timeGreeting(lang, userName);
    setMessages([
      {
        id: newId(),
        role: "assistant",
        content: greeting,
        timestamp: Date.now(),
        flowId: "welcome",
      },
    ]);
    // Fire the first proper step a tick later so the greeting feels distinct.
    // Override the welcome.greet step's trailing question with the
    // language- and visit-aware opening — chips stay the same.
    const greetStep = welcome.steps[welcome.start];
    const opening = OPENING_QUESTIONS[lang][isReturning ? "returning" : "firstTime"];
    const contextualGreetStep: FlowStep = {
      ...greetStep,
      message: greetStep.message.replace(
        /Bata bhai, tu trader kaisa hai\?/,
        opening,
      ),
    };
    setTimeout(() => pushAssistant(contextualGreetStep, welcome.id), 350);
    if (typeof window !== "undefined") {
      localStorage.setItem(SEEN_INTRO_KEY, "1");
    }
  }, [pushAssistant, user]);

  const open = useCallback(() => {
    setIsOpen(true);
    setUnreadCount(0);
    seedWelcome();
  }, [seedWelcome]);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => {
    setIsOpen((v) => {
      if (!v) {
        setUnreadCount(0);
        seedWelcome();
      }
      return !v;
    });
  }, [seedWelcome]);

  const reset = useCallback(() => {
    setMessages([]);
    setFlowState(null);
    hasSeededRef.current = false;
    hasIntroducedRef.current = false;
    sessionIdRef.current = newId();
    if (typeof window !== "undefined") {
      sessionStorage.setItem(SESSION_KEY, sessionIdRef.current);
    }
    // Re-seed welcome on the next open or immediately if already open.
    const welcome = FLOWS.welcome;
    const lang = lastLangRef.current;
    const userName =
      user?.full_name?.split(" ")[0] ||
      user?.email?.split("@")[0] ||
      "bhai";
    const isReturning =
      typeof window !== "undefined" &&
      localStorage.getItem(SEEN_INTRO_KEY) !== null;
    const greeting = timeGreeting(lang, userName);
    setMessages([
      {
        id: newId(),
        role: "assistant",
        content: greeting,
        timestamp: Date.now(),
        flowId: "welcome",
      },
    ]);
    const greetStep = welcome.steps[welcome.start];
    const opening = OPENING_QUESTIONS[lang][isReturning ? "returning" : "firstTime"];
    const contextualGreetStep: FlowStep = {
      ...greetStep,
      message: greetStep.message.replace(
        /Bata bhai, tu trader kaisa hai\?/,
        opening,
      ),
    };
    setTimeout(() => pushAssistant(contextualGreetStep, welcome.id), 200);
    hasSeededRef.current = true;
  }, [pushAssistant, user]);

  /**
   * Static-flow fallback: triggered when the AI endpoint returns 503,
   * 5xx, or network error. Mirrors the pre-Phase-1B routing so the
   * chat keeps working when Claude is unreachable.
   *
   * Defined before `sendUserText` so the React strict-hooks rule is
   * happy with the captured closure.
   */
  const fallbackToStaticFlow = useCallback(
    (text: string) => {
      const lang: Language = detectLanguage(text);
      lastLangRef.current = lang;
      const isEmotional = detectEmotionalDistress(text);
      const intents = detectIntents(text);
      const faq = isEmotional ? null : findBestFaq(text);
      const userName =
        user?.full_name?.split(" ")[0] ||
        user?.email?.split("@")[0] ||
        "bhai";

      if (isEmotional) {
        const lossIntake = FLOWS.support.steps.loss_intake;
        pushAssistant(lossIntake, "support");
        return;
      }
      if (faq) {
        const msg: ChatMessage = {
          id: newId(),
          role: "assistant",
          content: getFaqAnswer(faq, lang),
          timestamp: Date.now(),
          options: intentChips(intents, /* compact */ true),
        };
        setMessages((prev) => [...prev, msg]);
        return;
      }
      // Generic warm fallback in the user's language. Note: we drop
      // the persona intro here — by the time we hit this path we've
      // usually already greeted the user via the welcome flow.
      const fallback = FALLBACK_MESSAGES[lang];
      const ack: ChatMessage = {
        id: newId(),
        role: "assistant",
        content:
          intents.length > 0
            ? fallback.intentMatched(friendlyIntentList(intents, lang))
            : fallback.generic(userName),
        timestamp: Date.now(),
        options: intentChips(intents),
      };
      setMessages((prev) => [...prev, ack]);
      setFlowState(null);
    },
    [pushAssistant, user],
  );

  // Free-text routing — Phase 1B (Claude):
  //   1. Push user message + show typing indicator.
  //   2. POST to /api/algomitra/messages (Claude call).
  //   3. On success → render assistant text + AI suggestions as chips.
  //   4. On 429 → friendly rate-limit toast + WhatsApp escalation chips.
  //   5. On 503 / network error → fall back to static flow library.
  const sendUserText = useCallback(
    (text: string) => {
      pushUser(text);
      hasIntroducedRef.current = true;
      setIsThinking(true);

      void (async () => {
        try {
          const ai = await sendToAI(sessionIdRef.current, text, false);
          if (ai.tone === "crisis") {
            toast.error(
              "Mental health > money, bhai. iCall: 9152987821 (free, confidential).",
              { duration: 8000 },
            );
          }
          const reply: ChatMessage = {
            id: ai.assistant_message_id || newId(),
            role: "assistant",
            content: ai.message,
            timestamp: Date.now(),
            options:
              ai.suggestions.length > 0
                ? suggestionsToOptions(ai.suggestions)
                : undefined,
          };
          setMessages((prev) => [...prev, reply]);
          setFlowState(null);
        } catch (e) {
          // 429 — daily quota hit. Show the message + escalation, no fallback.
          if (e instanceof ApiError && e.status === 429) {
            const msg: ChatMessage = {
              id: newId(),
              role: "assistant",
              content: e.detail,
              timestamp: Date.now(),
              options: [
                {
                  label: "WhatsApp founder",
                  emoji: "💬",
                  action: { kind: "escalate", channel: "whatsapp" },
                },
                {
                  label: "Calendly slot book",
                  emoji: "📅",
                  action: { kind: "escalate", channel: "calendly" },
                },
              ],
            };
            setMessages((prev) => [...prev, msg]);
            return;
          }

          // Anything else → degrade to the static flow library.
          fallbackToStaticFlow(text);
        } finally {
          setIsThinking(false);
        }
      })();
    },
    [fallbackToStaticFlow, pushUser],
  );

  const sendUserImage = useCallback(
    (dataUrl: string, fileName: string) => {
      pushUser(`📸 Screenshot (${fileName})`, dataUrl);
      // Image alone has no text to detect from; reuse the last detected
      // language for this session, defaulting to Hinglish.
      const lang = lastLangRef.current;
      setTimeout(() => {
        const ack: ChatMessage = {
          id: newId(),
          role: "assistant",
          content: IMAGE_ACK_MESSAGES[lang],
          timestamp: Date.now(),
          options: [
            { label: "WhatsApp founder", emoji: "💬", action: { kind: "escalate", channel: "whatsapp" } },
            { label: "Calendly slot book", emoji: "📅", action: { kind: "escalate", channel: "calendly" } },
          ],
        };
        setMessages((prev) => [...prev, ack]);
      }, 400);
    },
    [pushUser],
  );

  const selectOption = useCallback(
    (option: FlowOption) => {
      // Echo the user's choice as their bubble for clarity.
      pushUser(option.label);

      const a = option.action;
      switch (a.kind) {
        case "next": {
          // Magic step name from intentChips() — "Specific Question" chip
          // re-engages the user instead of routing into a flow.
          if (a.nextStep === "__ask_for_question__") {
            const prompt: ChatMessage = {
              id: newId(),
              role: "assistant",
              content:
                "Bilkul bhai, type kar de — chahe kitna bhi specific ho. Main suntha hoon, detailed jawaab dunga. ✏️",
              timestamp: Date.now(),
            };
            setTimeout(() => {
              setMessages((prev) => [...prev, prompt]);
            }, 200);
            setFlowState(null);
            return;
          }
          const fid = flowState?.flowId ?? "welcome";
          const flow = FLOWS[fid] as Flow;
          const step = flow.steps[a.nextStep];
          if (step) setTimeout(() => pushAssistant(step, fid), 250);
          return;
        }
        case "switch_flow": {
          const flow = FLOWS[a.flowId];
          const step = flow.steps[a.nextStep ?? flow.start];
          if (step) setTimeout(() => pushAssistant(step, a.flowId), 250);
          return;
        }
        case "request_image": {
          const prompt: ChatMessage = {
            id: newId(),
            role: "assistant",
            content:
              "Image upload kar — neeche wala 🖼️ icon click kar. Max 4 MB, koi bhi screenshot chalega.",
            timestamp: Date.now(),
          };
          setTimeout(() => {
            setMessages((prev) => [...prev, prompt]);
          }, 200);
          return;
        }
        case "open_url": {
          if (a.url.startsWith("http")) {
            window.open(a.url, "_blank", "noopener");
          } else {
            router.push(a.url);
            setIsOpen(false);
          }
          return;
        }
        case "escalate": {
          const map = {
            whatsapp: ALGOMITRA_ESCALATION.whatsappUrl,
            calendly: ALGOMITRA_ESCALATION.calendlyUrl,
            email: ALGOMITRA_ESCALATION.emailUrl,
          } as const;
          const url = map[a.channel];
          if (a.channel === "email") {
            window.location.href = url;
          } else {
            window.open(url, "_blank", "noopener");
          }
          const ack: ChatMessage = {
            id: newId(),
            role: "assistant",
            content:
              a.channel === "whatsapp"
                ? "WhatsApp khol diya — wahan reply ka wait karte hain. Idhar bhi available hoon."
                : a.channel === "calendly"
                  ? "Calendly khul gayi — slot book kar le, founder direct call karenge."
                  : "Email client khol diya — message bhej de.",
            timestamp: Date.now(),
          };
          setTimeout(() => {
            setMessages((prev) => [...prev, ack]);
          }, 200);
          return;
        }
        case "end": {
          const ack: ChatMessage = {
            id: newId(),
            role: "assistant",
            content:
              "Theek hai bhai — main yahin hoon. Kuch bhi atak jaye, chat khol lena. 🤝",
            timestamp: Date.now(),
          };
          setTimeout(() => {
            setMessages((prev) => [...prev, ack]);
          }, 200);
          setFlowState(null);
          return;
        }
        case "restart": {
          reset();
          return;
        }
        case "chat_send": {
          // AI-suggested chip — send the label as a new free-text turn.
          sendUserText(a.text);
          return;
        }
      }
    },
    // sendUserText is defined above; intentional dep cycle is fine —
    // both functions are useCallback-stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [flowState, pushAssistant, pushUser, reset, router],
  );

  // Active options: latest assistant message's options, if any.
  const activeOptions = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "assistant" && m.options) return m.options;
      if (m.role === "user") return undefined;
    }
    return undefined;
  }, [messages]);

  // Track unread when new assistant messages arrive while widget is closed.
  const lastSeenLengthRef = useRef(0);
  useEffect(() => {
    if (isOpen) {
      lastSeenLengthRef.current = messages.length;
      return;
    }
    const newAssistant = messages
      .slice(lastSeenLengthRef.current)
      .filter((m) => m.role === "assistant").length;
    if (newAssistant > 0) {
      setUnreadCount((c) => c + newAssistant);
      lastSeenLengthRef.current = messages.length;
    }
  }, [messages, isOpen]);

  return {
    isOpen,
    open,
    close,
    toggle,
    reset,
    unreadCount,
    messages,
    activeOptions,
    isThinking,
    sendUserText,
    sendUserImage,
    selectOption,
  };
}
