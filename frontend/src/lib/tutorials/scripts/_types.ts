/**
 * Tutorial video script content shape.
 *
 * Each topic ships with BOTH a Hindi-only and English-only version
 * (separate full scripts — NOT one with translations interleaved).
 * Word count targets 200-300 wpm for natural conversational pace.
 *
 * Style: L&T-engineer authentic voice, conversational, "main aapko
 * dikhata hu" tone. NOT corporate, NOT hype.
 */
export interface ScriptSection {
  /** Start timestamp in seconds */
  time_start: number;
  /** End timestamp in seconds */
  time_end: number;
  /** What the narrator says (verbatim) */
  narration: string;
  /** What's happening on screen — for the editor */
  screen_action: string;
  /** B-roll suggestion if cutaway shot needed */
  b_roll_suggested: string;
}

export interface LanguageScript {
  intro: string;
  sections: ScriptSection[];
  outro: string;
  total_word_count: number;
}

export interface TutorialScript {
  topic: string;

  /** Target final video length in seconds */
  duration_target_seconds: number;

  hindi_script: LanguageScript;
  english_script: LanguageScript;

  thumbnail_text_options: string[];
  hashtags: string[];
  target_audience: string;
  prerequisites: string[];
}
