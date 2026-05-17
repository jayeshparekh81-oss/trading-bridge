/**
 * FAQItem — single question card with click-to-expand answer.
 *
 * Controlled component: the parent (FAQAccordion) owns the expanded
 * state for the whole list, so multiple items can be open at once.
 *
 * Answer text is rendered as a paragraph with minimal markdown
 * affordance — backticks and **bold** get inline styling. We
 * deliberately do NOT pull in a full markdown parser; the FAQ
 * content stays prose-first and the few formatting cues we use are
 * handled inline below to keep the bundle small.
 */

"use client";

import { ChevronDown } from "lucide-react";
import { useMemo } from "react";

import type { FAQ } from "@/lib/help/faq-content";
import type { Lang } from "./LangToggle";

export interface FAQItemProps {
  faq: FAQ;
  lang: Lang;
  isOpen: boolean;
  onToggle: () => void;
}

export function FAQItem({ faq, lang, isOpen, onToggle }: FAQItemProps) {
  const question = lang === "hi" ? faq.question_hi : faq.question_en;
  const rawAnswer = lang === "hi" ? faq.answer_hi : faq.answer_en;
  const answer = useMemo(() => renderInlineMd(rawAnswer), [rawAnswer]);

  return (
    <div
      data-testid="help-faq-item"
      data-faq-id={faq.id}
      data-faq-open={isOpen ? "true" : "false"}
      className="rounded-xl border border-white/10 bg-neutral-900/50 supports-backdrop-filter:backdrop-blur-md transition-colors hover:border-white/15"
    >
      <button
        type="button"
        onClick={onToggle}
        data-testid="help-faq-toggle"
        aria-expanded={isOpen}
        className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left"
      >
        <span className="text-sm font-medium text-neutral-100">{question}</span>
        <ChevronDown
          aria-hidden="true"
          className={`mt-0.5 h-4 w-4 shrink-0 text-neutral-400 transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>
      {isOpen && (
        <div
          data-testid="help-faq-answer"
          className="border-t border-white/5 px-4 py-3 text-sm leading-relaxed text-neutral-300"
        >
          {answer}
        </div>
      )}
    </div>
  );
}

// ─── Inline markdown ────────────────────────────────────────────────
// Two affordances only:
//   `code`     → <code> with monospaced styling
//   **bold**   → <strong> bold
// Everything else is rendered as plain text. Keep this tiny — full
// markdown gets pulled in via a real parser if/when the content team
// needs lists, links, tables.

function renderInlineMd(text: string): React.ReactNode {
  const tokens = tokenize(text);
  return tokens.map((t, i) => {
    if (t.kind === "code") {
      return (
        <code
          key={i}
          className="rounded bg-white/5 px-1 py-0.5 font-mono text-[12px] text-emerald-300"
        >
          {t.value}
        </code>
      );
    }
    if (t.kind === "bold") {
      return (
        <strong key={i} className="font-semibold text-neutral-100">
          {t.value}
        </strong>
      );
    }
    return <span key={i}>{t.value}</span>;
  });
}

type Token = { kind: "text" | "code" | "bold"; value: string };

function tokenize(text: string): Token[] {
  // Combined regex: capture either `code` or **bold** spans.
  const re = /`([^`]+)`|\*\*([^*]+)\*\*/g;
  const tokens: Token[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      tokens.push({ kind: "text", value: text.slice(last, m.index) });
    }
    if (m[1] !== undefined) {
      tokens.push({ kind: "code", value: m[1] });
    } else if (m[2] !== undefined) {
      tokens.push({ kind: "bold", value: m[2] });
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    tokens.push({ kind: "text", value: text.slice(last) });
  }
  return tokens;
}
