/**
 * The first-timer guided path (founder, 26 Sep 2026): one decision per screen, a
 * progress bar, a safe default, a way forward AND a way back on every screen, errors as
 * the never-stuck card, AlgoMitra beside every step, and the running dashboard with the
 * broker-stop truth, billed P&L and a confirmed STOP EVERYTHING.
 *
 * The screen payloads are the SERVER's real output (tests/guided/fixtures/states.json,
 * dumped by backend/scripts/guided_fixture_dump.py) — never a hand-made copy.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ApiError } from "@/shared/api/client";

const STATES = JSON.parse(readFileSync(join(process.cwd(), "tests/guided/fixtures/states.json"), "utf8"));

const guidedApi = vi.hoisted(() => ({
  publicStart: vi.fn(), state: vi.fn(), choose: vi.fn(), back: vi.fn(), broker: vi.fn(), ask: vi.fn(),
  confirm: vi.fn(), running: vi.fn(), stopPreview: vi.fn(), stop: vi.fn(), signup: vi.fn(), restart: vi.fn(),
}));
vi.mock("@/lib/guided-path", async (orig) => {
  const real = await orig<typeof import("@/lib/guided-path")>();
  return { ...real, guidedApi };
});

import * as lib from "@/lib/guided-path";
import { GuidedPath } from "@/components/guided/guided-path";
import { RunningDashboard } from "@/components/guided/guided-running";
import StartPage from "@/app/start/page";

const JARGON = /(Traceback|Exception|stack trace|HTTP \d{3}|status code|undefined|null\b|\bNaN\b|OAuth|endpoint|JSON|webhook)/i;

beforeEach(() => {
  Object.values(guidedApi).forEach((f) => f.mockReset());
  localStorage.setItem("tb_access_token", "t");
});
afterEach(() => {
  localStorage.clear();
  delete process.env[lib.GUIDED_FLAG];
});

// ── the lib ──────────────────────────────────────────────────────────────────

describe("guided-path lib", () => {
  it("is OFF unless the flag is exactly 1", () => {
    expect(lib.guidedPathEnabled()).toBe(false);
    process.env[lib.GUIDED_FLAG] = "true";
    expect(lib.guidedPathEnabled()).toBe(false);
    process.env[lib.GUIDED_FLAG] = "1";
    expect(lib.guidedPathEnabled()).toBe(true);
  });

  it("rupees in the customer's own digits, NOT MEASURED stays words", () => {
    expect(lib.inr(631765)).toBe("Rs 6,31,765");
    expect(lib.inr(63105)).toBe("Rs 63,105");
    expect(lib.inr("NOT MEASURED")).toBe("NOT MEASURED");
    expect(lib.inr(null)).toBe("NOT MEASURED");
    expect(lib.inr("abc")).toBe("NOT MEASURED");
  });

  it("the server's envelope wins; anything else becomes plain words with a way forward", () => {
    const env = { kind: "WRONG_CREDENTIALS", what_happened: "a", what_it_means: "b", what_to_do: "c", action: null, back: null, contact: null };
    expect(lib.toCustomerError(new ApiError(400, "x", { error: env }))).toEqual(env);
    const off = lib.toCustomerError(new ApiError(0, "Network error — is the backend running?"));
    expect(off.kind).toBe("OFFLINE");
    expect(off.what_happened).not.toMatch(/backend/i);
    expect(lib.toCustomerError(new ApiError(401, "Session expired")).kind).toBe("SIGNED_OUT");
    const u = lib.toCustomerError(new TypeError("Cannot read properties of undefined"));
    expect(u.kind).toBe("UNKNOWN");
    expect(JSON.stringify(u)).not.toMatch(/Cannot read|TypeError/);
    expect(u.contact?.send).toMatch(/token KABHI mat bhejna/);
  });

  it("signup errors are mapped once, in Hinglish", () => {
    expect(lib.signupError(new ApiError(409, "Email already registered: a@b.c")).kind).toBe("EMAIL_TAKEN");
    expect(lib.signupError(new ApiError(400, "Weak password: minimum 8 characters")).what_to_do).toMatch(/8 akshar/);
    expect(lib.signupError(new ApiError(422, "value is not a valid email")).kind).toBe("BAD_FORM");
  });

  it("the password rules are shown before typing and match the server's", () => {
    const ok = (pw: string) => lib.PASSWORD_RULES.every((r) => r.ok(pw, { email: "ravi@example.com", name: "Ravi Kumar" }));
    expect(ok("Guided@2026x")).toBe(true);
    expect(ok("guided@2026x")).toBe(false);     // no capital
    expect(ok("Ravi@2026xx")).toBe(false);      // contains the email local part / name
    expect(ok("Gu@1")).toBe(false);             // too short
  });

  it("the local mirror only remembers a real step", () => {
    lib.rememberStep("SIZE");
    expect(lib.lastStep()).toBe("SIZE");
    localStorage.setItem("tb_guided_last_step", "<script>");
    expect(lib.lastStep()).toBeNull();
  });
});

// ── every screen: bar, one decision, why, default, forward, back, guide ─────

describe("every screen has a way forward, a way back and the guide", () => {
  for (const key of ["BROKER", "STRATEGY", "VEHICLE", "STRIKE", "SIZE", "SUMMARY", "CONFIRM"]) {
    it(`${key}`, async () => {
      guidedApi.state.mockResolvedValue(STATES[key]);
      render(<GuidedPath />);
      await screen.findByTestId("guided");
      expect(screen.getByTestId("guided").dataset.step).toBe(key);
      expect(screen.getByTestId("guided-progress-count").textContent).toMatch(/Kadam \d \/ [78]/);   // 7 for futures (STRIKE not needed), 8 when an option vehicle needs it
      expect(screen.getByTestId("guided-title").textContent).toBe(STATES[key].screen.title);
      expect(screen.getByTestId("guided-why").textContent).toContain(STATES[key].screen.why);
      expect(screen.getByTestId("guided-next")).toBeTruthy();
      expect(screen.getByTestId("guided-back")).toBeTruthy();
      expect(screen.getByTestId("guided-guide-text").textContent!.length).toBeGreaterThan(20);
      expect(document.body.textContent).not.toMatch(JARGON);
    });
  }

  it("the signup screen (no account yet) shows the rules before typing and a login way out", async () => {
    localStorage.clear();
    guidedApi.publicStart.mockResolvedValue({ step: "SIGNUP", progress: STATES.BROKER.progress.map((p: { step: string }) => ({ ...p, state: p.step === "SIGNUP" ? "CURRENT" : p.step === "STRIKE" ? "NOT_NEEDED" : "TODO" })),
      screen: { step: "SIGNUP", title: "Account banao", decision: "Naam, email aur password — bas.", why: "w", default_note: "" },
      guide: { text: "Account banao: ...", kind: "EXPLAIN", flags: [], warnings: [] } });
    render(<GuidedPath />);
    await screen.findByTestId("screen-SIGNUP");
    expect(screen.getByTestId("signup-rules").textContent).toMatch(/8 ya zyada akshar/);
    expect((screen.getByTestId("guided-next") as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId("guided-back").getAttribute("href")).toBe("/login?next=/start");
  });

  it("defaults arrive pre-chosen: FUTURES selected, locked ones say why, OTM selected", async () => {
    guidedApi.state.mockResolvedValue(STATES.VEHICLE);
    const { unmount } = render(<GuidedPath />);
    await screen.findByTestId("screen-VEHICLE");
    expect(screen.getByTestId("vehicle-FUTURES").getAttribute("aria-checked")).toBe("true");
    const locked = screen.getByTestId("vehicle-OPTION_BUY") as HTMLButtonElement;
    expect(locked.disabled).toBe(true);
    expect(locked.textContent).toMatch(/Band hai/);
    unmount();
    guidedApi.state.mockResolvedValue(STATES.STRIKE);
    render(<GuidedPath />);
    await screen.findByTestId("screen-STRIKE");
    expect(screen.getByTestId("strike-OTM").getAttribute("aria-checked")).toBe("true");
  });

  it("the SIZE screen only LOOKS UP the server's numbers for each choice", async () => {
    guidedApi.state.mockResolvedValue(STATES.SIZE);
    render(<GuidedPath />);
    await screen.findByTestId("screen-SIZE");
    expect(screen.getByTestId("size-numbers").textContent).toContain("Rs 6,31,765");
    fireEvent.click(screen.getByLabelText("Badhao"));
    expect(screen.getByTestId("size-lots").textContent).toBe("4 lot");
    expect(screen.getByTestId("size-numbers").textContent).toContain(lib.inr(STATES.SIZE.screen.by_lots["4"].minimum_capital));
  });

  it("Back asks the server and keeps the work (the draft comes back intact)", async () => {
    guidedApi.state.mockResolvedValue(STATES.SUMMARY);
    guidedApi.back.mockResolvedValue({ ...STATES.SIZE, draft: { ...STATES.SIZE.draft, lots: 4 } });
    render(<GuidedPath />);
    await screen.findByTestId("summary");
    await act(async () => { fireEvent.click(screen.getByTestId("guided-back")); });
    expect(guidedApi.back).toHaveBeenCalledWith("SUMMARY");
    await screen.findByTestId("screen-SIZE");
    expect(screen.getByTestId("size-lots").textContent).toBe("4 lot");
  });

  it("the confirm button stays shut until the tick", async () => {
    guidedApi.state.mockResolvedValue(STATES.CONFIRM);
    render(<GuidedPath />);
    await screen.findByTestId("screen-CONFIRM");
    const next = screen.getByTestId("guided-next") as HTMLButtonElement;
    expect(next.disabled).toBe(true);
    fireEvent.click(screen.getByTestId("confirm-ack"));
    expect(next.disabled).toBe(false);
  });
});

// ── the never-stuck rule ────────────────────────────────────────────────────

describe("errors land somewhere clear", () => {
  const envelope = (kind: string, step: string | null) => ({ error: {
    kind, what_happened: "Dhan ne yeh Client ID / token maana nahi.", what_it_means: "Aapka account abhi juda nahi hai.",
    what_to_do: "web.dhan.co par naya token banao.", action: { label: "Dobara try karo", href: null, step }, back: null, contact: null } });

  it("wrong credentials: the card, the fix, and the form is still there", async () => {
    guidedApi.state.mockResolvedValue(STATES.BROKER);
    guidedApi.broker.mockRejectedValue(new ApiError(400, "x", envelope("WRONG_CREDENTIALS", "BROKER")));
    render(<GuidedPath />);
    await screen.findByTestId("screen-BROKER");
    fireEvent.change(screen.getByLabelText("Dhan Client ID"), { target: { value: "1000000001" } });
    fireEvent.change(screen.getByLabelText(/Dhan access token/), { target: { value: "x".repeat(120) } });
    await act(async () => { fireEvent.click(screen.getByTestId("guided-next")); });
    const card = await screen.findByTestId("guided-error");
    expect(card.dataset.kind).toBe("WRONG_CREDENTIALS");
    expect(screen.getByTestId("guided-error-todo").textContent).toMatch(/naya token/);
    expect((screen.getByLabelText("Dhan Client ID") as HTMLInputElement).value).toBe("1000000001");   // work kept
    expect(screen.getByTestId("guided-next")).toBeTruthy();
  });

  it("the network itself failing is still a card with a retry, not a blank", async () => {
    guidedApi.state.mockRejectedValue(new ApiError(0, "Network error — is the backend running?"));
    render(<GuidedPath />);
    const card = await screen.findByTestId("guided-error");
    expect(card.dataset.kind).toBe("OFFLINE");
    expect(card.textContent).not.toMatch(/backend/i);
    expect(screen.getByTestId("guided-error-action").textContent).toMatch(/Dobara/);
  });

  it("a closed tab resumes on the server's step and says so while loading", async () => {
    localStorage.setItem("tb_guided_last_step", "SIZE");
    let resolve!: (v: unknown) => void;
    guidedApi.state.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<GuidedPath />);
    expect(screen.getByTestId("guided-loading").textContent).toMatch(/jahan ruke the/);
    await act(async () => { resolve(STATES.SIZE); });
    expect((await screen.findByTestId("guided")).dataset.step).toBe("SIZE");
  });
});

// ── running ────────────────────────────────────────────────────────────────

const RUNNING: lib.Running = {
  strategy: "BSE Ltd Momentum (test listing)", running: true, stopped: false, is_paper: true,
  paper_line: "Abhi sab PAPER (practice) hai — asli order nahi ja raha.", lots: 2,
  market: { open: false, line: "Market abhi band hai — agla session 28 Sep 2026 ko 09:15 IST se." },
  broker: { state: "ACTIVE", line: "Dhan juda hai (abhi check kiya).", action: null },
  positions: [{ symbol: "BSE-OCT2026-FUT", side: "buy", quantity: 400, avg_price: "3200.00", opened_at: null }],
  positions_line: "1 position khuli hai.",
  stop: { verdict: "PROTECTED", line: "Position khuli: buy 400 BSE-OCT2026-FUT. Stop broker par RAKHA HAI (order 1), 40s pehle Dhan se check kiya.", verified_at: "2026-09-26T10:00:00+00:00", source: "GET /v2/forever/orders" },
  today_pnl: { line: "Aaj koi trade band nahi hua — aaj ka P&L Rs 0.", measured: true, net_inr: "0.00", gross_inr: "0.00", billed_charges_inr: "0.00" },
  stop_everything: { enabled: true },
};

describe("the running dashboard", () => {
  it("shows the position, the broker-stop truth, today's billed P&L and STOP EVERYTHING", async () => {
    guidedApi.running.mockResolvedValue(RUNNING);
    render(<RunningDashboard onGoto={() => {}} />);
    await screen.findByTestId("running");
    expect(screen.getByTestId("running-position").textContent).toMatch(/LONG 400/);
    expect(screen.getByTestId("running-stop").dataset.verdict).toBe("PROTECTED");
    expect(screen.getByTestId("running-pnl").textContent).toMatch(/Rs 0/);
    expect(screen.getByTestId("running-paper").textContent).toMatch(/PAPER/);
    expect(screen.getByTestId("stop-everything")).toBeTruthy();
  });

  it("STOP EVERYTHING explains first, changes nothing on 'Nahi', and acts only on 'Haan'", async () => {
    guidedApi.running.mockResolvedValue(RUNNING);
    guidedApi.stopPreview.mockResolvedValue({ confirm_token: "tok", expires_in_s: 120, positions: 1, paper: true,
      lines: ["1. Aapki strategy turant band hogi — koi NAYI entry nahi hogi.", "2. Khuli 1 position market bhaav par band ki jayegi."] });
    guidedApi.stop.mockResolvedValue({ stopped: true, lines: ["Band: 1 position band hui."], restart_line: "Dobara chalu sirf aap." });
    render(<RunningDashboard onGoto={() => {}} />);
    await screen.findByTestId("stop-everything");
    await act(async () => { fireEvent.click(screen.getByTestId("stop-everything")); });
    expect((await screen.findByTestId("stop-lines")).textContent).toMatch(/NAYI entry nahi/);
    fireEvent.click(screen.getByTestId("stop-no"));
    expect(guidedApi.stop).not.toHaveBeenCalled();
    await act(async () => { fireEvent.click(screen.getByTestId("stop-everything")); });
    await screen.findByTestId("stop-yes");
    await act(async () => { fireEvent.click(screen.getByTestId("stop-yes")); });
    expect(guidedApi.stop).toHaveBeenCalledWith("tok");
    expect((await screen.findByTestId("stop-result")).textContent).toMatch(/Band: 1 position/);
  });

  it("an unknown stop says so and never shows green", async () => {
    guidedApi.running.mockResolvedValue({ ...RUNNING, stop: { verdict: "NOT MEASURED", line: "Dhan par stop hai ya nahi — abhi pakka pata nahi.", verified_at: null, source: "" } });
    render(<RunningDashboard onGoto={() => {}} />);
    const card = await screen.findByTestId("running-stop");
    expect(card.dataset.verdict).toBe("NOT MEASURED");
    expect(card.className).not.toMatch(/border-profit/);
  });

  it("STOP switched off says so in words; an expired token offers the fix", async () => {
    guidedApi.running.mockResolvedValue({ ...RUNNING, stop_everything: { enabled: false },
      broker: { state: "EXPIRED", line: "Dhan token expire ho gaya — naya daalo.", action: { label: "Naya token daalo", href: null, step: "BROKER" } } });
    const onGoto = vi.fn();
    render(<RunningDashboard onGoto={onGoto} />);
    expect((await screen.findByTestId("stop-off")).textContent).toMatch(/chalu nahi/);
    fireEvent.click(screen.getByText("Naya token daalo"));
    expect(onGoto).toHaveBeenCalledWith(expect.objectContaining({ step: "BROKER" }));
  });

  it("after STOP the dashboard says so and offers a deliberate restart (never a start button)", async () => {
    guidedApi.running.mockResolvedValue({ ...RUNNING, running: false, stopped: true, positions: [] });
    const onRestart = vi.fn();
    render(<RunningDashboard onGoto={() => {}} onRestart={onRestart} />);
    const box = await screen.findByTestId("stopped");
    expect(box.textContent).toMatch(/band hai/);
    expect(screen.queryByTestId("stop-everything")).toBeNull();
    fireEvent.click(screen.getByTestId("restart"));
    expect(onRestart).toHaveBeenCalled();
  });

  it("a failed load is a card with a way forward", async () => {
    guidedApi.running.mockRejectedValue(new ApiError(0, "Network error"));
    render(<RunningDashboard onGoto={() => {}} />);
    expect((await screen.findByTestId("guided-error")).dataset.kind).toBe("OFFLINE");
  });
});

describe("/start behind its flag", () => {
  it("OFF renders one honest line and nothing else", () => {
    render(<StartPage />);
    expect(screen.getByTestId("guided-off").textContent).toMatch(/abhi chalu nahi/);
    expect(screen.queryByTestId("guided")).toBeNull();
  });
  it("ON renders the path", async () => {
    process.env[lib.GUIDED_FLAG] = "1";
    guidedApi.state.mockResolvedValue(STATES.STRATEGY);
    render(<StartPage />);
    await waitFor(() => expect(screen.getByTestId("guided").dataset.step).toBe("STRATEGY"));
  });
});
