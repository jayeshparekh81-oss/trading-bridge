"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { X } from "lucide-react";
import glossaryJson from "@/data/glossary.json";
import { useLanguage, type Lang } from "@/contexts/LanguageContext";

interface LangFields {
  term: string;
  label: string;
  explanation?: string;
  example?: string;
  audio_script?: string;
}

interface GlossaryWord {
  id: string;
  category: string;
  en: LangFields;
  hi: LangFields;
  gu: LangFields;
}

const WORDS = (glossaryJson as { words: GlossaryWord[] }).words;
const WORD_BY_ID = new Map<string, GlossaryWord>(WORDS.map((w) => [w.id, w]));

const BUTTON_LABELS: Record<Lang, { listen: string; video: string; comingSoon: string }> = {
  en: { listen: "Listen", video: "Watch video", comingSoon: "Coming soon" },
  hi: { listen: "Sun lo", video: "Video joya", comingSoon: "Jaldi aa raha" },
  gu: { listen: "Sun lo", video: "Video joya", comingSoon: "Jaldi aave che" },
};

const TRADETRI_BLUE = "#185FA5";

function pickFields(word: GlossaryWord, lang: Lang): { fields: LangFields; effectiveLang: Lang } {
  const primary = word[lang];
  // A language entry counts as "present" if it has a label.
  // English entries legitimately have only term+label — no explanation/example yet.
  if (primary?.label) {
    return { fields: primary, effectiveLang: lang };
  }
  // Translation truly missing for the selected lang — fall back to English.
  if (word.en?.label) {
    return { fields: word.en, effectiveLang: "en" };
  }
  // Last-resort fallback to the other Indian language.
  const other: Lang = lang === "hi" ? "gu" : "hi";
  return { fields: word[other], effectiveLang: other };
}

interface SamjhoWordProps {
  termId: string;
  children?: ReactNode;
}

export function SamjhoWord({ termId, children }: SamjhoWordProps) {
  const { lang } = useLanguage();
  const [open, setOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const popupRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const word = WORD_BY_ID.get(termId);

  // Track viewport for mobile vs desktop popup style.
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 599px)");
    const update = () => setIsMobile(mql.matches);
    update();
    mql.addEventListener("change", update);
    return () => mql.removeEventListener("change", update);
  }, []);

  // Close on Escape + click outside, lock body scroll while open.
  useEffect(() => {
    if (!open) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (popupRef.current && !popupRef.current.contains(target) && !triggerRef.current?.contains(target)) {
        setOpen(false);
      }
    };

    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
      document.body.style.overflow = prevOverflow;
    };
  }, [open]);

  const display = useMemo(() => {
    if (!word) return null;
    const { fields, effectiveLang } = pickFields(word, lang);
    return { fields, effectiveLang };
  }, [word, lang]);

  const handleListen = useCallback(() => {
    if (!word || !display) return;
    const script = display.fields.audio_script ?? word.en.term;
    // eslint-disable-next-line no-console
    console.log("Audio coming soon:", script);
  }, [word, display]);

  const handleOpen = useCallback(() => {
    if (!word) return;
    try {
      // eslint-disable-next-line no-console
      console.log({ event: "samjho_tap", termId, lang, time: new Date() });
    } catch {
      // analytics is best-effort, never crash the UI
    }
    setOpen(true);
  }, [word, termId, lang]);

  // Glossary miss — render fallback children, warn once.
  if (!word) {
    if (typeof window !== "undefined") {
      // eslint-disable-next-line no-console
      console.warn(`[SamjhoWord] termId "${termId}" not found in glossary`);
    }
    return <>{children}</>;
  }

  if (!display) return <>{children}</>;

  const { fields, effectiveLang } = display;
  const labels = BUTTON_LABELS[lang];

  try {
    return (
      <>
        <button
          ref={triggerRef}
          type="button"
          onClick={handleOpen}
          lang={effectiveLang}
          className="inline cursor-pointer bg-transparent p-0 font-inherit text-inherit transition-colors hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
          style={{
            textDecoration: "underline dotted 1.5px",
            textDecorationColor: TRADETRI_BLUE,
            textUnderlineOffset: "3px",
            color: "inherit",
          }}
          aria-label={`Samjho: ${fields.label}`}
          aria-haspopup="dialog"
          aria-expanded={open}
        >
          <span style={{ color: TRADETRI_BLUE }}>{fields.label}</span>
        </button>

        {open && (
          <SamjhoPopup
            ref={popupRef}
            isMobile={isMobile}
            lang={lang}
            effectiveLang={effectiveLang}
            fields={fields}
            labels={labels}
            onClose={() => setOpen(false)}
            onListen={handleListen}
          />
        )}
      </>
    );
  } catch (err) {
    // Defensive: any render-time issue shouldn't crash the host page.
    // eslint-disable-next-line no-console
    console.error("[SamjhoWord] render error:", err);
    return <>{children ?? word.en.label}</>;
  }
}

interface SamjhoPopupProps {
  ref: React.Ref<HTMLDivElement>;
  isMobile: boolean;
  lang: Lang;
  effectiveLang: Lang;
  fields: LangFields;
  labels: { listen: string; video: string; comingSoon: string };
  onClose: () => void;
  onListen: () => void;
}

function SamjhoPopup({
  ref,
  isMobile,
  effectiveLang,
  fields,
  labels,
  onClose,
  onListen,
}: SamjhoPopupProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={fields.label}
      className="fixed inset-0 z-[100] flex items-end justify-center sm:items-center sm:p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.45)" }}
    >
      <div
        ref={ref}
        lang={effectiveLang}
        className={
          isMobile
            ? "w-full animate-[samjho-slide-up_220ms_ease-out] rounded-t-2xl bg-white p-5 text-gray-900 shadow-xl"
            : "w-full max-w-[400px] animate-[samjho-fade-in_180ms_ease-out] rounded-2xl bg-white p-6 text-gray-900 shadow-xl"
        }
        style={{ boxShadow: "0 12px 40px rgba(0,0,0,0.18)" }}
      >
        <div className="flex items-start justify-between gap-3">
          <h3
            className="text-xl font-semibold leading-tight"
            style={{ color: TRADETRI_BLUE }}
          >
            {fields.label}
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="-m-1 rounded-full p-1 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {fields.term && fields.term !== fields.label && (
          <p className="mt-1 text-sm text-gray-500">{fields.term}</p>
        )}

        {fields.explanation && (
          <p className="mt-3 text-base leading-relaxed text-gray-800">
            {fields.explanation}
          </p>
        )}

        {fields.example && (
          <div
            className="mt-4 rounded-lg p-3 text-sm leading-relaxed"
            style={{
              backgroundColor: "#EAF2FB",
              color: "#0F2A44",
            }}
          >
            <div className="text-xs font-medium uppercase tracking-wide" style={{ color: TRADETRI_BLUE }}>
              Example
            </div>
            <div className="mt-1">{fields.example}</div>
          </div>
        )}

        <div className="mt-5 flex gap-2">
          <button
            type="button"
            onClick={onListen}
            className="flex-1 rounded-lg px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ backgroundColor: TRADETRI_BLUE }}
          >
            🔊 {labels.listen}
          </button>
          <button
            type="button"
            disabled
            title={labels.comingSoon}
            className="flex-1 cursor-not-allowed rounded-lg border border-gray-200 px-4 py-2 text-sm font-semibold text-gray-400"
          >
            🎬 {labels.video}
          </button>
        </div>

        <p className="mt-2 text-center text-[11px] text-gray-400">
          {labels.comingSoon}
        </p>
      </div>

      {/* Local keyframes — scoped via name so they don't collide with anything global. */}
      <style>{`
        @keyframes samjho-slide-up {
          from { transform: translateY(24px); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }
        @keyframes samjho-fade-in {
          from { transform: scale(0.97); opacity: 0; }
          to   { transform: scale(1);    opacity: 1; }
        }
      `}</style>
    </div>
  );
}

export default SamjhoWord;
