"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { findBestFaq } from "@/lib/algomitra-faqs";
import {
  FLOWS,
  type Flow,
  type FlowId,
  type FlowOption,
  type FlowStep,
} from "@/lib/algomitra-flows";
import {
  ALGOMITRA_ESCALATION,
  timeGreeting,
} from "@/lib/algomitra-personality";

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

// ─── Backend logging (best-effort, never throws) ────────────────────────

async function logToBackend(
  sessionId: string,
  msg: ChatMessage,
): Promise<void> {
  try {
    await api.post("/algomitra/messages", {
      session_id: sessionId,
      role: msg.role,
      content: msg.content,
      flow_id: msg.flowId ?? null,
      flow_step: msg.flowStep ?? null,
      has_image: Boolean(msg.imageDataUrl),
    });
  } catch (e) {
    // Logging is best-effort. Anonymous users (401) and network errors
    // must not break the chat. Surface only unexpected statuses.
    if (e instanceof ApiError && e.status !== 401 && e.status !== 0) {
      console.warn("algomitra log failed", e.status, e.detail);
    }
  }
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

  const sessionIdRef = useRef<string>("");
  const hasSeededRef = useRef(false);

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
      void logToBackend(sessionIdRef.current, msg);
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
    void logToBackend(sessionIdRef.current, msg);
  }, []);

  // Seed the welcome flow with greeting + first step. Called from open()
  // and reset() — kept out of useEffect so React's strict cascading-render
  // rule stays satisfied.
  const seedWelcome = useCallback(() => {
    if (hasSeededRef.current) return;
    hasSeededRef.current = true;
    const welcome = FLOWS.welcome;
    const greeting = timeGreeting();
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
    setTimeout(() => pushAssistant(welcome.steps[welcome.start], welcome.id), 350);
    if (typeof window !== "undefined") {
      localStorage.setItem(SEEN_INTRO_KEY, "1");
    }
  }, [pushAssistant]);

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
    sessionIdRef.current = newId();
    if (typeof window !== "undefined") {
      sessionStorage.setItem(SESSION_KEY, sessionIdRef.current);
    }
    // Re-seed welcome on the next open or immediately if already open.
    const welcome = FLOWS.welcome;
    const greeting = timeGreeting();
    setMessages([
      {
        id: newId(),
        role: "assistant",
        content: greeting,
        timestamp: Date.now(),
        flowId: "welcome",
      },
    ]);
    setTimeout(() => pushAssistant(welcome.steps[welcome.start], welcome.id), 200);
    hasSeededRef.current = true;
  }, [pushAssistant]);

  // Free-text user message: try FAQ match first; otherwise hand-off line.
  const sendUserText = useCallback(
    (text: string) => {
      pushUser(text);
      const faq = findBestFaq(text);
      setTimeout(() => {
        if (faq) {
          const msg: ChatMessage = {
            id: newId(),
            role: "assistant",
            content: faq.answer,
            timestamp: Date.now(),
            flowId: undefined,
          };
          setMessages((prev) => [...prev, msg]);
          void logToBackend(sessionIdRef.current, msg);
          return;
        }
        // No FAQ match → suggest flows + escalation.
        const handoff: ChatMessage = {
          id: newId(),
          role: "assistant",
          content:
            "Bhai, exact match nahi mil raha. Niche ke options se pick kar — ya WhatsApp pe founder se directly baat kar le.",
          timestamp: Date.now(),
          options: [
            { label: "Setup help", emoji: "🔌", action: { kind: "switch_flow", flowId: "setup" } },
            { label: "Error fix", emoji: "🛠️", action: { kind: "switch_flow", flowId: "error" } },
            { label: "Education", emoji: "📚", action: { kind: "switch_flow", flowId: "education" } },
            { label: "WhatsApp founder", emoji: "💬", action: { kind: "escalate", channel: "whatsapp" } },
          ],
          flowId: undefined,
        };
        setMessages((prev) => [...prev, handoff]);
        setFlowState(null);
        void logToBackend(sessionIdRef.current, handoff);
      }, 400);
    },
    [pushUser],
  );

  const sendUserImage = useCallback(
    (dataUrl: string, fileName: string) => {
      pushUser(`📸 Screenshot bheji (${fileName})`, dataUrl);
      setTimeout(() => {
        const ack: ChatMessage = {
          id: newId(),
          role: "assistant",
          content:
            "Bhai photo mil gayi. 🙏 Founder ko pass kar diya — wo dekhke jaldi reply karenge.\n\nAgar urgent hai toh WhatsApp pe ping bhi kar de — direct hi pakdo.",
          timestamp: Date.now(),
          options: [
            { label: "WhatsApp founder", emoji: "💬", action: { kind: "escalate", channel: "whatsapp" } },
            { label: "Calendly slot book", emoji: "📅", action: { kind: "escalate", channel: "calendly" } },
          ],
        };
        setMessages((prev) => [...prev, ack]);
        void logToBackend(sessionIdRef.current, ack);
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
            void logToBackend(sessionIdRef.current, prompt);
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
            void logToBackend(sessionIdRef.current, ack);
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
            void logToBackend(sessionIdRef.current, ack);
          }, 200);
          setFlowState(null);
          return;
        }
        case "restart": {
          reset();
          return;
        }
      }
    },
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
    sendUserText,
    sendUserImage,
    selectOption,
  };
}
