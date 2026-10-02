/**
 * Login / signup errors in human words (founder's rule, 26 Sep 2026, point 8:
 * "what happened, why, and exactly what to do next — never a code").
 *
 * The server answers in English engineer words ("Invalid email or password",
 * "Email already registered: …", "Weak password: at least one digit", a 422
 * validation list). This turns each into ONE line a first-timer can act on — in the
 * customer's language (English by default, Hinglish when chosen; 2 Oct 2026). Decided by
 * the HTTP status the server already sends — never by parsing prose, except the
 * weak-password reasons, which are a fixed list the server owns
 * (backend/app/core/security_ext.py) and are translated one by one.
 */

import { signupClosedLine } from "@/lib/signup-status";
import { authCopy } from "@/lib/i18n/copy/auth";
import { currentLang, fill, type Lang } from "@/lib/i18n/core";
import { ApiError } from "@/shared/api/client";

type AuthKey = keyof typeof authCopy.dicts.en;
const word = (lang: Lang, k: AuthKey, vars?: Record<string, string | number>) => fill(authCopy.pick(lang)[k], vars);

/** The password rules the server enforces, in the words the register form shows. */
export function passwordRules(lang: Lang): { key: string; label: string; test: (pw: string) => boolean }[] {
  return [
    { key: "len", label: word(lang, "rule_len"), test: (pw) => pw.length >= 8 },
    { key: "upper", label: word(lang, "rule_upper"), test: (pw) => /[A-Z]/.test(pw) },
    { key: "lower", label: word(lang, "rule_lower"), test: (pw) => /[a-z]/.test(pw) },
    { key: "digit", label: word(lang, "rule_digit"), test: (pw) => /\d/.test(pw) },
    { key: "symbol", label: word(lang, "rule_symbol"), test: (pw) => /[^A-Za-z0-9]/.test(pw) },
  ];
}
/** The Hinglish list, for the tests that pin it by name. */
export const PASSWORD_RULES = passwordRules("hinglish");

const WEAK_REASON: [RegExp, AuthKey][] = [
  [/minimum 8 characters/i, "weak_len"],
  [/uppercase/i, "weak_upper"],
  [/lowercase/i, "weak_lower"],
  [/digit/i, "weak_digit"],
  [/special character/i, "weak_symbol"],
  [/common-passwords/i, "weak_common"],
  [/email local part/i, "weak_email"],
  [/user's name/i, "weak_name"],
];

function weakPassword(detail: string, lang: Lang): string {
  const parts = WEAK_REASON.filter(([re]) => re.test(detail)).map(([, k]) => word(lang, k));
  return parts.length ? word(lang, "weak_prefix", { parts: parts.join(", ") }) : word(lang, "weak_generic");
}

/** One line for a login failure, in `lang` (default: the customer's current language). */
export function loginError(err: unknown, lang: Lang = currentLang()): string {
  if (!(err instanceof ApiError)) return word(lang, "err_login_network");
  switch (err.status) {
    case 401:
      return word(lang, "err_login_401");
    case 429: {
      const secs = Number(/(\d+)\s*seconds?/i.exec(err.detail)?.[1] ?? NaN);
      const wait = Number.isFinite(secs) ? word(lang, "wait_minutes", { n: Math.max(1, Math.ceil(secs / 60)) }) : word(lang, "wait_short");
      return word(lang, "err_login_429", { wait });
    }
    case 403:
      return word(lang, "err_login_403");
    case 422:
      return word(lang, "err_login_422");
    case 0:
      return err.detail;
    default:
      return err.status >= 500 ? err.detail : word(lang, "err_login_default");
  }
}

/** One line for a signup failure, in `lang` (default: the customer's current language). */
export function registerError(err: unknown, lang: Lang = currentLang()): string {
  if (!(err instanceof ApiError)) return word(lang, "err_reg_network");
  switch (err.status) {
    case 403:
      // 1 Oct 2026: signup closed to the public (the server's own line when it is in the customer's
      // language, else ours).
      return lang === "hinglish" && err.detail && /band/i.test(err.detail) ? err.detail : signupClosedLine(lang);
    case 409:
      return word(lang, "err_reg_409");
    case 400:
      return /weak password/i.test(err.detail) ? weakPassword(err.detail, lang) : word(lang, "err_reg_400");
    case 422:
      return word(lang, "err_reg_422");
    case 429:
      return word(lang, "err_reg_429");
    case 0:
      return err.detail;
    default:
      return err.status >= 500 ? err.detail : word(lang, "err_reg_default");
  }
}

/** The Hinglish lines by name (the 26 Sep tests pin them). */
export const loginErrorHi = (err: unknown): string => loginError(err, "hinglish");
export const registerErrorHi = (err: unknown): string => registerError(err, "hinglish");
