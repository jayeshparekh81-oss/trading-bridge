/**
 * Test helper: make the device's EXPLICIT language choice, exactly as a tap on the switch would
 * (value + the "chosen" marker). Tests that pin Hinglish words describe an account that CHOSE
 * Hinglish — since 2 Oct 2026 the default is English, so they must say so.
 */
import { CHOSEN_KEY, STORAGE_KEY, type Lang } from "@/contexts/LanguageContext";

export function forceLang(lang: Lang): void {
  window.localStorage.setItem(STORAGE_KEY, lang);
  window.localStorage.setItem(CHOSEN_KEY, "1");
}

export function clearLang(): void {
  window.localStorage.removeItem(STORAGE_KEY);
  window.localStorage.removeItem(CHOSEN_KEY);
}
