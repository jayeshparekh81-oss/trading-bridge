/**
 * THE REGRESSION THE FOUNDER DEMANDED — no celebratory copy over a loss.
 *
 * WHAT HAPPENED (2026-09-09)
 * ──────────────────────────
 * The coach read CUMULATIVE `total_pnl`, subtracted a per-IST-day baseline
 * it had stored in localStorage that morning, and reacted to the
 * difference. The tracking cut-off archived the pre-cut history; `total_pnl`
 * moved from -195,830.51 to 0.00; the difference came out +195,830.51; the
 * band selector chose "profit-huge" and the screen said
 *
 *     🚀 ₹1,95,831! Killer day.
 *
 * over a LOSS.
 *
 * WHY A "DON'T CELEBRATE NEGATIVES" GUARD ALONE WOULD NOT HAVE CAUGHT IT
 * ─────────────────────────────────────────────────────────────────────
 * No negative ever reached the formatter — the arithmetic handed it a large
 * POSITIVE. That defect is fixed at its source (the baseline is deleted;
 * `deriveTodayPnl` sums today's own rows). This suite covers the OTHER half:
 * the renderer was total over the wrong domain and would cheerfully build
 * celebratory copy out of any number handed to it, including
 * "🚀 -₹50,000! Killer day." and "+-₹50,000". A renderer that cannot be
 * talked into that is the last line of defence for the next arithmetic bug
 * nobody has written yet.
 *
 * HOW THIS SUITE IS BUILT — exhaustive, not example-based
 * ──────────────────────────────────────────────────────
 * The axes are enumerated from the MODULE'S OWN exported tables and asserted
 * equal to `Object.keys(REACTIONS)` IN BOTH DIRECTIONS, so a fifth language
 * (or an eighth trigger) cannot be added to the table and silently go
 * untested, nor be dropped from the table while the list still claims it.
 * Every (language × trigger × time-of-day) cell is then crossed with a
 * boundary-complete plus fuzzed set of NEGATIVE amounts.
 *
 * The positive control at the bottom is load-bearing: without it a marker
 * list that matched NOTHING ANYWHERE would pass this whole file vacuously.
 */

import { describe, expect, it } from "vitest";

import {
  REACTIONS,
  REACTION_LANGUAGES,
  REACTION_TIMES_OF_DAY,
  REACTION_TRIGGERS,
  TRIGGER_POLARITY,
  amountFitsTrigger,
  renderReaction,
  selectTrigger,
  type ReactionTriggerId,
} from "@/lib/algomitra-reactions";

// ─── The markers that must never appear over a loss ─────────────────────

/**
 * Named explicitly, per the founder. Each entry is one way the copy can
 * SOUND like good news. `ci: true` matches case-insensitively so "Killer"
 * also catches the Hinglish/Hindi/Gujarati "KILLER".
 *
 * The positive control asserts every one of these is reachable, so a typo
 * here fails the suite instead of quietly disarming a check.
 */
const CELEBRATORY_MARKERS: ReadonlyArray<{ label: string; needle: string; ci?: boolean }> = [
  { label: "rocket", needle: "🚀" },
  { label: "party", needle: "🎉" },
  { label: "fire", needle: "🔥" },
  { label: "Killer", needle: "killer", ci: true },
  { label: "Great", needle: "great", ci: true },
  { label: "superb", needle: "superb", ci: true },
  { label: "Nice", needle: "nice", ci: true },
  { label: "positive", needle: "positive", ci: true },
  { label: "plus-rupee", needle: "+₹" },
  { label: "badhiya", needle: "badhiya", ci: true },
  { label: "wah", needle: "wah", ci: true },
  { label: "comeback", needle: "comeback", ci: true },
  { label: "saras", needle: "સરસ" },
];

/**
 * Sign-mangling artefacts. These are not "celebration" — they are the
 * literal strings the old renderer produced when a negative was piped into
 * gain copy ("+-₹50,000", "-₹50,000 positive"). They must never appear in
 * ANY message, over a loss or a profit, so they get their own sweep.
 */
const MALFORMED_MONEY: readonly string[] = ["+-₹", "-₹", "₹-", "NaN", "Infinity", "undefined"];

function hits(message: string, m: { needle: string; ci?: boolean }): boolean {
  return m.ci
    ? message.toLowerCase().includes(m.needle.toLowerCase())
    : message.includes(m.needle);
}

function celebratoryMarkersIn(message: string): string[] {
  return CELEBRATORY_MARKERS.filter((m) => hits(message, m)).map((m) => m.label);
}

// ─── The negative amounts ───────────────────────────────────────────────

/**
 * Boundary-complete around every threshold `selectTrigger` uses (-100,
 * -1000, -5000) plus the zero edge, the real number from the incident, and
 * the numeric extremes a bad subtraction can actually produce.
 */
const BOUNDARY_NEGATIVES: readonly number[] = [
  -0.0000001,
  -0.01,
  -0.5,
  -1,
  -99,
  -99.99,
  -100,
  -100.01,
  -101,
  -499.99,
  -500,
  -999,
  -999.99,
  -1000,
  -1000.01,
  -1001,
  -2999.99,
  -3000,
  -4999.99,
  -5000,
  -5000.01,
  -9999.99,
  -10000,
  -10000.01,
  -195830.51, // THE number. The screen said "🚀 ₹1,95,831! Killer day."
  -195830.5,
  -1_00_00_000,
  -Number.MAX_SAFE_INTEGER,
  -Number.MIN_VALUE,
  -Number.EPSILON,
];

/** Deterministic fuzz — a seeded LCG, so a failure is always reproducible. */
function fuzzedNegatives(count: number, seed = 20260909): number[] {
  let state = seed;
  const next = () => {
    state = (state * 1664525 + 1013904223) % 4294967296;
    return state / 4294967296;
  };
  const out: number[] = [];
  for (let i = 0; i < count; i++) {
    // Log-uniform across ₹0.01 … ₹1 crore, so every band is well sampled.
    const magnitude = Math.pow(10, next() * 9 - 2);
    out.push(-Math.round(magnitude * 100) / 100);
  }
  return out;
}

const NEGATIVE_AMOUNTS: readonly number[] = [
  ...BOUNDARY_NEGATIVES,
  ...fuzzedNegatives(120),
];

const GAIN_TRIGGERS = REACTION_TRIGGERS.filter(
  (t) => TRIGGER_POLARITY[t] === "gain",
);
const LOSS_TRIGGERS = REACTION_TRIGGERS.filter(
  (t) => TRIGGER_POLARITY[t] === "loss",
);

// ─── 1. The enumeration is the real enumeration ─────────────────────────

describe("the axes are enumerated from the module's own tables", () => {
  it("REACTION_LANGUAGES and Object.keys(REACTIONS) agree in BOTH directions", () => {
    const declared = [...REACTION_LANGUAGES].sort();
    const actual = Object.keys(REACTIONS).sort();
    expect(actual).toEqual(declared);
    // Spelled out both ways on purpose: a one-directional subset check would
    // pass while a fifth language sat in the table untested.
    for (const lang of REACTION_LANGUAGES) expect(actual).toContain(lang);
    for (const lang of actual) expect(declared).toContain(lang);
    expect(actual).toHaveLength(declared.length);
  });

  it("REACTION_TRIGGERS and the per-language keys agree in BOTH directions", () => {
    const declared = [...REACTION_TRIGGERS].sort();
    for (const lang of REACTION_LANGUAGES) {
      const actual = Object.keys(REACTIONS[lang]).sort();
      expect(actual).toEqual(declared);
      for (const t of REACTION_TRIGGERS) expect(actual).toContain(t);
      for (const t of actual) expect(declared).toContain(t);
    }
  });

  it("every trigger declares a polarity, and every polarity names a trigger", () => {
    expect(Object.keys(TRIGGER_POLARITY).sort()).toEqual([...REACTION_TRIGGERS].sort());
    expect(GAIN_TRIGGERS.length + LOSS_TRIGGERS.length).toBe(REACTION_TRIGGERS.length);
    expect(GAIN_TRIGGERS.length).toBeGreaterThan(0);
    expect(LOSS_TRIGGERS.length).toBeGreaterThan(0);
  });

  it("the cross product is non-trivial (the sweeps below are not empty)", () => {
    const cells =
      REACTION_LANGUAGES.length * REACTION_TRIGGERS.length * REACTION_TIMES_OF_DAY.length;
    expect(cells).toBe(112);
    expect(NEGATIVE_AMOUNTS.length).toBeGreaterThanOrEqual(150);
    expect(NEGATIVE_AMOUNTS.every((a) => a < 0)).toBe(true);
  });
});

// ─── 2. THE FOUNDER'S TEST: no celebration on a loss, anywhere ──────────

describe("no negative amount can produce celebratory copy", () => {
  it("refuses every (language × gain-trigger × time-of-day × negative) cell", () => {
    let cells = 0;
    for (const lang of REACTION_LANGUAGES) {
      for (const trigger of GAIN_TRIGGERS) {
        for (const tod of REACTION_TIMES_OF_DAY) {
          for (const amount of NEGATIVE_AMOUNTS) {
            const rendered = renderReaction(trigger, amount, lang, tod);
            cells++;
            if (rendered !== null) {
              throw new Error(
                `celebratory copy rendered over a loss: ${lang}/${trigger}/${tod} ` +
                  `@ ${amount} → ${JSON.stringify(rendered.message)}`,
              );
            }
          }
        }
      }
    }
    expect(cells).toBe(
      REACTION_LANGUAGES.length *
        GAIN_TRIGGERS.length *
        REACTION_TIMES_OF_DAY.length *
        NEGATIVE_AMOUNTS.length,
    );
  });

  it("loss copy over a negative carries NO celebratory marker", () => {
    for (const lang of REACTION_LANGUAGES) {
      for (const trigger of LOSS_TRIGGERS) {
        for (const tod of REACTION_TIMES_OF_DAY) {
          for (const amount of NEGATIVE_AMOUNTS) {
            const rendered = renderReaction(trigger, amount, lang, tod);
            expect(rendered).not.toBeNull();
            const found = celebratoryMarkersIn(rendered!.message);
            if (found.length > 0) {
              throw new Error(
                `loss copy sounds like a win: ${lang}/${trigger}/${tod} @ ${amount} ` +
                  `carries [${found.join(", ")}] → ${JSON.stringify(rendered!.message)}`,
              );
            }
          }
        }
      }
    }
  });

  it("the exact incident amount (-195830.51) is silent in every gain cell", () => {
    for (const lang of REACTION_LANGUAGES) {
      for (const trigger of GAIN_TRIGGERS) {
        for (const tod of REACTION_TIMES_OF_DAY) {
          expect(renderReaction(trigger, -195830.51, lang, tod)).toBeNull();
        }
      }
    }
    // And the sentence the screen actually printed is now unreachable.
    for (const lang of REACTION_LANGUAGES) {
      for (const tod of REACTION_TIMES_OF_DAY) {
        expect(renderReaction("profit-huge", -195830.51, lang, tod)).toBeNull();
      }
    }
  });

  it("the guarded table cannot be bypassed by calling REACTIONS directly", () => {
    // renderReaction is a thin wrapper; the guard lives in the TABLE, so a
    // caller reaching past the wrapper gets the same refusal.
    for (const lang of REACTION_LANGUAGES) {
      for (const trigger of GAIN_TRIGGERS) {
        for (const tod of REACTION_TIMES_OF_DAY) {
          expect(REACTIONS[lang][trigger](-50000, tod)).toBeNull();
        }
      }
    }
  });

  it("positive amounts cannot produce loss copy either (the mirror mispairing)", () => {
    for (const lang of REACTION_LANGUAGES) {
      for (const trigger of LOSS_TRIGGERS) {
        for (const tod of REACTION_TIMES_OF_DAY) {
          for (const amount of NEGATIVE_AMOUNTS) {
            expect(renderReaction(trigger, -amount, lang, tod)).toBeNull();
          }
        }
      }
    }
  });

  it("no rendered message anywhere contains a sign-mangled money string", () => {
    const amounts = [...NEGATIVE_AMOUNTS, ...NEGATIVE_AMOUNTS.map((a) => -a), 0];
    for (const lang of REACTION_LANGUAGES) {
      for (const trigger of REACTION_TRIGGERS) {
        for (const tod of REACTION_TIMES_OF_DAY) {
          for (const amount of amounts) {
            const rendered = renderReaction(trigger, amount, lang, tod);
            if (rendered === null) continue;
            for (const bad of MALFORMED_MONEY) {
              if (rendered.message.includes(bad)) {
                throw new Error(
                  `malformed money "${bad}" in ${lang}/${trigger}/${tod} @ ${amount} ` +
                    `→ ${JSON.stringify(rendered.message)}`,
                );
              }
            }
          }
        }
      }
    }
  });

  it("renderReaction is TOTAL — it never throws and never returns undefined", () => {
    const amounts = [
      ...NEGATIVE_AMOUNTS,
      ...NEGATIVE_AMOUNTS.map((a) => -a),
      0,
      -0,
      NaN,
      Infinity,
      -Infinity,
    ];
    for (const lang of REACTION_LANGUAGES) {
      for (const trigger of REACTION_TRIGGERS) {
        for (const tod of REACTION_TIMES_OF_DAY) {
          for (const amount of amounts) {
            const rendered = renderReaction(trigger, amount, lang, tod);
            expect(rendered === null || typeof rendered.message === "string").toBe(true);
            if (rendered) {
              expect(rendered.triggerId).toBe(trigger);
              expect(rendered.message.length).toBeGreaterThan(0);
            }
          }
        }
      }
    }
  });

  it("a non-finite amount renders NOTHING, in every cell", () => {
    for (const lang of REACTION_LANGUAGES) {
      for (const trigger of REACTION_TRIGGERS) {
        for (const tod of REACTION_TIMES_OF_DAY) {
          for (const amount of [NaN, Infinity, -Infinity]) {
            expect(amountFitsTrigger(trigger, amount)).toBe(false);
            expect(renderReaction(trigger, amount, lang, tod)).toBeNull();
          }
        }
      }
    }
  });
});

// ─── 3. The selector never routes a loss to a gain band ─────────────────

describe("selectTrigger keeps losses in loss bands", () => {
  it("never returns a gain trigger for a negative amount", () => {
    const prevs = [null, -195830.51, -5000, -1, 0, 1, 5000, 195830.51];
    for (const amount of NEGATIVE_AMOUNTS) {
      for (const prev of prevs) {
        const trigger = selectTrigger(amount, prev);
        if (trigger === null) continue;
        expect(TRIGGER_POLARITY[trigger]).toBe("loss");
      }
    }
  });

  it("whatever it returns is a pairing renderReaction will actually render", () => {
    const amounts = [...NEGATIVE_AMOUNTS, ...NEGATIVE_AMOUNTS.map((a) => -a), 0];
    const prevs = [null, -5000, -1, 0, 1, 5000];
    for (const amount of amounts) {
      for (const prev of prevs) {
        const trigger: ReactionTriggerId | null = selectTrigger(amount, prev);
        if (trigger === null) continue;
        expect(amountFitsTrigger(trigger, amount)).toBe(true);
        expect(renderReaction(trigger, amount, "en", "morning")).not.toBeNull();
      }
    }
  });
});

// ─── 4. POSITIVE CONTROL — the marker list is not vacuous ───────────────

describe("positive control: the markers this suite bans are really reachable", () => {
  /** Every message the table can produce for a genuine profit. */
  const positiveMessages: string[] = [];
  for (const lang of REACTION_LANGUAGES) {
    for (const trigger of GAIN_TRIGGERS) {
      for (const tod of REACTION_TIMES_OF_DAY) {
        for (const amount of [500, 3000, 10000, 195830.51]) {
          const rendered = renderReaction(trigger, amount, lang, tod);
          if (rendered) positiveMessages.push(rendered.message);
        }
      }
    }
  }

  it("gain copy actually renders for positive amounts", () => {
    expect(positiveMessages.length).toBe(
      REACTION_LANGUAGES.length * GAIN_TRIGGERS.length * REACTION_TIMES_OF_DAY.length * 4,
    );
  });

  it.each(CELEBRATORY_MARKERS.map((m) => [m.label, m] as const))(
    "the %s marker appears in real profit copy (so banning it means something)",
    (_label, marker) => {
      const found = positiveMessages.some((msg) => hits(msg, marker));
      expect(found).toBe(true);
    },
  );

  it("celebratory copy IS produced somewhere — the ban is not passing vacuously", () => {
    const celebratory = positiveMessages.filter(
      (msg) => celebratoryMarkersIn(msg).length > 0,
    );
    expect(celebratory.length).toBe(positiveMessages.length);
  });

  it("the very sentence from the incident renders for a real +₹1,95,831 profit", () => {
    const rendered = renderReaction("profit-huge", 195830.51, "en", "afternoon");
    expect(rendered).not.toBeNull();
    expect(rendered!.message).toBe("🚀 ₹1,95,831! Killer day.");
    // ...and is refused for the loss that actually occurred.
    expect(renderReaction("profit-huge", -195830.51, "en", "afternoon")).toBeNull();
  });
});
