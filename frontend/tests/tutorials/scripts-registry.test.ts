import { describe, it, expect } from "vitest";
import {
  SCRIPTS,
  SCRIPT_COUNT,
  getScript,
  listScripts,
  type TutorialScript,
  type LanguageScript,
} from "@/lib/tutorials/scripts";

const EXPECTED_COUNT = 10;
const MIN_DURATION = 240;
const MAX_DURATION = 360;
const MIN_WPM = 55;
const MAX_WPM = 100;

const assertLanguageShape = (topic: string, lang: "hindi" | "english", s: LanguageScript) => {
  expect(s.intro.length, `${topic}.${lang}.intro`).toBeGreaterThan(50);
  expect(s.outro.length, `${topic}.${lang}.outro`).toBeGreaterThan(50);
  expect(Array.isArray(s.sections), `${topic}.${lang}.sections array`).toBe(true);
  expect(s.sections.length, `${topic}.${lang}: ≥3 sections`).toBeGreaterThanOrEqual(3);
  for (let i = 0; i < s.sections.length; i++) {
    const sec = s.sections[i];
    expect(sec.time_start, `${topic}.${lang}.sections[${i}].time_start`).toBeGreaterThanOrEqual(0);
    expect(sec.time_end, `${topic}.${lang}.sections[${i}].time_end > time_start`).toBeGreaterThan(sec.time_start);
    expect(sec.narration.length, `${topic}.${lang}.sections[${i}].narration`).toBeGreaterThan(40);
    expect(sec.screen_action.length, `${topic}.${lang}.sections[${i}].screen_action`).toBeGreaterThan(15);
    expect(sec.b_roll_suggested.length, `${topic}.${lang}.sections[${i}].b_roll`).toBeGreaterThan(10);
  }
  expect(s.total_word_count, `${topic}.${lang}.total_word_count`).toBeGreaterThan(150);
};

const assertShape = (topic: string, sc: TutorialScript) => {
  expect(sc.topic, `${topic}: topic match`).toBe(topic);
  expect(sc.duration_target_seconds, `${topic}: duration in 4-6 min`).toBeGreaterThanOrEqual(MIN_DURATION);
  expect(sc.duration_target_seconds, `${topic}: duration in 4-6 min`).toBeLessThanOrEqual(MAX_DURATION);
  assertLanguageShape(topic, "hindi", sc.hindi_script);
  assertLanguageShape(topic, "english", sc.english_script);
  expect(sc.thumbnail_text_options.length, `${topic}: ≥2 thumbnails`).toBeGreaterThanOrEqual(2);
  expect(sc.hashtags.length, `${topic}: ≥3 hashtags`).toBeGreaterThanOrEqual(3);
  expect(sc.target_audience.length, `${topic}: target_audience`).toBeGreaterThan(10);
  expect(Array.isArray(sc.prerequisites), `${topic}: prerequisites array`).toBe(true);

  // Word-per-minute sanity check (60-100 wpm for natural pace with screen actions)
  const enWpm = (sc.english_script.total_word_count / sc.duration_target_seconds) * 60;
  const hiWpm = (sc.hindi_script.total_word_count / sc.duration_target_seconds) * 60;
  expect(enWpm, `${topic}: EN wpm in ${MIN_WPM}-${MAX_WPM}`).toBeGreaterThanOrEqual(MIN_WPM);
  expect(enWpm, `${topic}: EN wpm in ${MIN_WPM}-${MAX_WPM}`).toBeLessThanOrEqual(MAX_WPM);
  expect(hiWpm, `${topic}: HI wpm in ${MIN_WPM}-${MAX_WPM}`).toBeGreaterThanOrEqual(MIN_WPM);
  expect(hiWpm, `${topic}: HI wpm in ${MIN_WPM}-${MAX_WPM}`).toBeLessThanOrEqual(MAX_WPM);
};

describe("tutorial scripts registry", () => {
  it("registers the expected number of scripts", () => {
    expect(SCRIPT_COUNT).toBe(EXPECTED_COUNT);
    expect(listScripts()).toHaveLength(EXPECTED_COUNT);
  });

  it("every script has a well-formed shape and natural pacing", () => {
    for (const [topic, sc] of Object.entries(SCRIPTS)) {
      assertShape(topic, sc);
    }
  });

  it("getScript returns null for unknown topic", () => {
    expect(getScript("does-not-exist")).toBeNull();
    expect(getScript("")).toBeNull();
  });

  it("section timestamps stay within duration target", () => {
    for (const [topic, sc] of Object.entries(SCRIPTS)) {
      for (const lang of ["hindi_script", "english_script"] as const) {
        const s = sc[lang];
        for (let i = 0; i < s.sections.length; i++) {
          expect(
            s.sections[i].time_end,
            `${topic}.${lang}.sections[${i}].time_end <= duration_target_seconds`,
          ).toBeLessThanOrEqual(sc.duration_target_seconds);
        }
      }
    }
  });
});
