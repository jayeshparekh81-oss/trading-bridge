/**
 * Login / signup errors in human words (founder's rule, 26 Sep 2026, point 8:
 * "what happened, why, and exactly what to do next — never a code").
 *
 * The server answers in English engineer words ("Invalid email or password",
 * "Email already registered: …", "Weak password: at least one digit", a 422
 * validation list). This turns each into ONE Hinglish line a first-timer can act on.
 * Decided by the HTTP status the server already sends — never by parsing prose,
 * except the weak-password reasons, which are a fixed list the server owns
 * (backend/app/core/security_ext.py) and are translated one by one.
 */

import { ApiError } from "@/shared/api/client";

/** The password rules the server enforces, in the words the register form shows. */
export const PASSWORD_RULES: { key: string; label: string; test: (pw: string) => boolean }[] = [
  { key: "len", label: "Kam se kam 8 akshar", test: (pw) => pw.length >= 8 },
  { key: "upper", label: "Ek bada akshar (A-Z)", test: (pw) => /[A-Z]/.test(pw) },
  { key: "lower", label: "Ek chhota akshar (a-z)", test: (pw) => /[a-z]/.test(pw) },
  { key: "digit", label: "Ek ank (0-9)", test: (pw) => /\d/.test(pw) },
  { key: "symbol", label: "Ek nishaan, jaise ! @ # $", test: (pw) => /[^A-Za-z0-9]/.test(pw) },
];

const WEAK_REASON_HI: [RegExp, string][] = [
  [/minimum 8 characters/i, "kam se kam 8 akshar"],
  [/uppercase/i, "ek bada akshar (A-Z)"],
  [/lowercase/i, "ek chhota akshar (a-z)"],
  [/digit/i, "ek ank (0-9)"],
  [/special character/i, "ek nishaan (jaise ! @ #)"],
  [/common-passwords/i, "yeh password bahut aam hai — koi aur chuno"],
  [/email local part/i, "password me apna email mat daalo"],
  [/user's name/i, "password me apna naam mat daalo"],
];

function weakPasswordHi(detail: string): string {
  const parts = WEAK_REASON_HI.filter(([re]) => re.test(detail)).map(([, hi]) => hi);
  return parts.length
    ? `Password thoda aur mazboot chahiye: ${parts.join(", ")}. Password badal ke dobara "Account banao" dabao.`
    : "Password thoda aur mazboot chahiye — upar ki saari line hari (✓) karo, phir dobara dabao.";
}

/** One Hinglish line for a login failure. */
export function loginErrorHi(err: unknown): string {
  if (!(err instanceof ApiError)) return "Login nahi ho paaya — internet dekho aur dobara try karo.";
  switch (err.status) {
    case 401:
      return "Email ya password match nahi hua. Dobara dhyan se type karo (Caps Lock band hai na dekh lo).";
    case 429: {
      const secs = Number(/(\d+)\s*seconds?/i.exec(err.detail)?.[1] ?? NaN);
      const wait = Number.isFinite(secs) ? `${Math.max(1, Math.ceil(secs / 60))} minute` : "thodi der";
      return `Kai baar galat password daala gaya, isliye account thodi der ke liye ruka hai. ${wait} baad dobara try karo.`;
    }
    case 403:
      return "Yeh account abhi band hai. Contact page se hume WhatsApp karo — hum dekh lenge.";
    case 422:
      return "Email sahi nahi lag raha — jaise naam@gmail.com. Theek karke dobara dabao.";
    case 0:
      return err.detail;
    default:
      return err.status >= 500 ? err.detail : "Login nahi ho paaya — dobara try karo. Phir bhi na ho to Contact page se WhatsApp karo.";
  }
}

/** One Hinglish line for a signup failure. */
export function registerErrorHi(err: unknown): string {
  if (!(err instanceof ApiError)) return "Account nahi ban paaya — internet dekho aur dobara try karo.";
  switch (err.status) {
    case 409:
      return "Is email se account pehle se bana hua hai. Neeche \"Login karo\" dabao.";
    case 400:
      return /weak password/i.test(err.detail) ? weakPasswordHi(err.detail) : "Kuch jaankari adhoori hai — upar ki har line bharo, phir dobara dabao.";
    case 422:
      return "Email sahi nahi lag raha — jaise naam@gmail.com. Theek karke dobara dabao.";
    case 429:
      return "Bahut jaldi-jaldi try hua. 1 minute ruk ke dobara dabao.";
    case 0:
      return err.detail;
    default:
      return err.status >= 500 ? err.detail : "Account nahi ban paaya — dobara try karo. Phir bhi na bane to Contact page se WhatsApp karo.";
  }
}
