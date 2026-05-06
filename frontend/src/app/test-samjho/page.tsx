"use client";

import { SamjhoWord } from "@/components/SamjhoWord";
import { useLanguage, type Lang } from "@/contexts/LanguageContext";

const LANG_BUTTONS: { code: Lang; label: string }[] = [
  { code: "gu", label: "ગુજરાતી" },
  { code: "hi", label: "हिंदी" },
  { code: "en", label: "English" },
];

export default function TestSamjhoPage() {
  const { lang, setLang } = useLanguage();

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold">Samjho Button — Test Page</h1>
        <p className="text-sm text-muted-foreground">
          Tap any underlined word to see its meaning in your language.
        </p>
      </header>

      <section
        className="flex flex-wrap gap-2"
        role="group"
        aria-label="Language switcher"
      >
        {LANG_BUTTONS.map(({ code, label }) => {
          const active = lang === code;
          return (
            <button
              key={code}
              type="button"
              onClick={() => setLang(code)}
              lang={code}
              className={
                "rounded-lg border px-4 py-2 text-sm font-medium transition-colors " +
                (active
                  ? "border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : "border-border bg-card hover:bg-accent")
              }
              aria-pressed={active}
            >
              {label}
            </button>
          );
        })}
      </section>

      <section className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <h2 className="mb-4 text-xl font-semibold">Iron Condor Strategy</h2>

        <div className="flex flex-col divide-y divide-border">
          <Row>
            <SamjhoWord termId="win_rate">Win Rate</SamjhoWord>
            <span className="font-mono">76%</span>
          </Row>

          <Row>
            <SamjhoWord termId="max_drawdown">Max Drawdown</SamjhoWord>
            <span className="font-mono">10%</span>
          </Row>

          <Row>
            <SamjhoWord termId="risk_reward">Risk-Reward</SamjhoWord>
            <span className="font-mono">1:4</span>
          </Row>

          <Row>
            <SamjhoWord termId="capital">Capital</SamjhoWord>
            <span className="font-mono">₹50,000</span>
          </Row>
        </div>
      </section>

      <p className="text-xs text-muted-foreground">
        Selected language is saved to <code>localStorage</code> under{" "}
        <code>tradetri_language</code>. Resize the browser below 600px to see
        the bottom-sheet popup style.
      </p>
    </main>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-3 text-base">
      {children}
    </div>
  );
}
