/**
 * THE LANGUAGE IS REMEMBERED PER ACCOUNT, ACROSS LOGOUT/LOGIN (founder, 2 Oct 2026, item 4),
 * and DEFAULT = ENGLISH for everyone who never chose (item 1).
 *
 * The contract, proven here against the EXACT calls the app makes (`PUT /users/me` with the
 * read-merge-written `notification_prefs`, then `refreshUser()`):
 *   1. a fresh device, no account → English, and NOTHING is written anywhere;
 *   2. a stored language WITHOUT the explicit marker (the 2 Oct morning build's forced Hinglish)
 *      is NOT a choice → English;
 *   3. an explicit tap on the switch → remembered on the device AND written to the account,
 *      merged over the server's existing prefs (the ladder, the toggles survive);
 *   4. the account's stored language WINS over the device when a user loads (applied, never
 *      written back);
 *   5. a device choice made before login is attached to an account that has none;
 *   6. logout keeps the device choice; the next login re-applies the account's.
 *
 * Twins (proven 2 Oct): drop the marker check → case 2 RED · spread the server prefs away → case 3 RED.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({ put: vi.fn(async () => ({})), get: vi.fn(), post: vi.fn() }));
vi.mock("@/shared/api/client", () => ({ api, ApiError: class extends Error {} }));

type Prefs = Record<string, unknown>;
const auth = vi.hoisted(() => ({
  user: null as null | { id: string; notification_prefs: Prefs },
  refreshUser: vi.fn(async () => undefined),
}));
vi.mock("@/lib/auth", () => ({
  useAuthOptional: () => ({ user: auth.user, refreshUser: auth.refreshUser }),
  useAuth: () => ({ user: auth.user, refreshUser: auth.refreshUser }),
}));

import { CHOSEN_KEY, LanguageProvider, STORAGE_KEY, useLanguage } from "@/contexts/LanguageContext";
import { ACCOUNT_LANG_KEY, LanguageAccountSync, readAccountLanguage } from "@/components/site/language-account-sync";
import { LanguageSwitch } from "@/components/site/language-switch";

function Probe() {
  const { lang, chosen } = useLanguage();
  return <output data-testid="lang" data-chosen={chosen ? "1" : "0"}>{lang}</output>;
}
function App() {
  return (
    <LanguageProvider>
      <LanguageAccountSync />
      <LanguageSwitch />
      <Probe />
    </LanguageProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  api.put.mockClear();
  auth.refreshUser.mockClear();
  auth.user = null;
});
afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe("the default and the explicit marker", () => {
  it("1. a fresh device, no account → English; nothing written", () => {
    render(<App />);
    expect(screen.getByTestId("lang")).toHaveTextContent("en");
    expect(screen.getByTestId("lang").dataset.chosen).toBe("0");
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(api.put).not.toHaveBeenCalled();
  });

  it("2. a stored language WITHOUT the marker (the forced 2 Oct Hinglish) is not a choice → English", () => {
    localStorage.setItem(STORAGE_KEY, "hinglish");
    render(<App />);
    expect(screen.getByTestId("lang")).toHaveTextContent("en");
    expect(api.put).not.toHaveBeenCalled();
  });

  it("the switch offers exactly the four options, English first", () => {
    render(<App />);
    const opts = [...screen.getByTestId("language-switch").querySelectorAll("option")].map((o) => o.textContent);
    expect(opts).toEqual(["English", "Hinglish", "हिन्दी", "ગુજરાતી"]);
  });
});

describe("remembered on the device and on the account", () => {
  it("3. an explicit tap → the device marker AND a merged PUT /users/me", async () => {
    auth.user = { id: "u1", notification_prefs: { email: true, telegram: false, _ui_ladder: { choice: "auto" } } };
    render(<App />);
    fireEvent.change(screen.getByTestId("language-switch"), { target: { value: "hinglish" } });
    expect(screen.getByTestId("lang")).toHaveTextContent("hinglish");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("hinglish");
    expect(localStorage.getItem(CHOSEN_KEY)).toBe("1");
    await waitFor(() => expect(api.put).toHaveBeenCalledTimes(1));
    expect(api.put).toHaveBeenCalledWith("/users/me", {
      notification_prefs: { email: true, telegram: false, _ui_ladder: { choice: "auto" }, [ACCOUNT_LANG_KEY]: "hinglish" },
    });
    await waitFor(() => expect(auth.refreshUser).toHaveBeenCalled());
  });

  it("4. the account's stored language WINS over the device, and is never written back", async () => {
    localStorage.setItem(STORAGE_KEY, "hinglish");
    localStorage.setItem(CHOSEN_KEY, "1");
    auth.user = { id: "u2", notification_prefs: { email: true, [ACCOUNT_LANG_KEY]: "gu" } };
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("lang")).toHaveTextContent("gu"));
    expect(localStorage.getItem(STORAGE_KEY)).toBe("gu");
    expect(api.put).not.toHaveBeenCalled();
  });

  it("5. a device choice made before login is attached to an account that has none", async () => {
    localStorage.setItem(STORAGE_KEY, "hi");
    localStorage.setItem(CHOSEN_KEY, "1");
    auth.user = { id: "u3", notification_prefs: { email: true } };
    render(<App />);
    expect(screen.getByTestId("lang")).toHaveTextContent("hi");
    await waitFor(() => expect(api.put).toHaveBeenCalledWith("/users/me", { notification_prefs: { email: true, [ACCOUNT_LANG_KEY]: "hi" } }));
  });

  it("6. logout keeps the device choice; the next login applies that account's own", async () => {
    auth.user = { id: "u4", notification_prefs: { [ACCOUNT_LANG_KEY]: "hinglish" } };
    const r = render(<App />);
    await waitFor(() => expect(screen.getByTestId("lang")).toHaveTextContent("hinglish"));
    // logout
    await act(async () => {
      auth.user = null;
      r.rerender(<App />);
    });
    expect(screen.getByTestId("lang")).toHaveTextContent("hinglish"); // the device remembers
    // login as a different account whose choice is English
    await act(async () => {
      auth.user = { id: "u5", notification_prefs: { [ACCOUNT_LANG_KEY]: "en" } };
      r.rerender(<App />);
    });
    await waitFor(() => expect(screen.getByTestId("lang")).toHaveTextContent("en"));
    expect(api.put).not.toHaveBeenCalled();
  });

  it("an account value that is not one of the four languages is ignored (never a crash, never applied)", () => {
    expect(readAccountLanguage({ [ACCOUNT_LANG_KEY]: "fr" })).toBeNull();
    expect(readAccountLanguage({ [ACCOUNT_LANG_KEY]: 7 })).toBeNull();
    expect(readAccountLanguage(null)).toBeNull();
    expect(readAccountLanguage({ [ACCOUNT_LANG_KEY]: "hinglish" })).toBe("hinglish");
  });
});
