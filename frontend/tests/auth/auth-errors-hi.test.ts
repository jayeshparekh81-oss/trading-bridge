/**
 * Login / signup errors reach the customer in human words (founder's rule, 26 Sep,
 * point 8). The server's English lines are the INPUT; none of them may be the OUTPUT.
 */
import { describe, expect, it } from "vitest";

import { ApiError, NETWORK_TROUBLE_HI } from "@/shared/api/client";
import { loginErrorHi, PASSWORD_RULES, registerErrorHi } from "@/lib/auth-errors";

const ENGLISH = /Invalid email or password|already registered|Weak password|Account locked|inactive|minimum 8 characters/i;

describe("login errors", () => {
  it.each([
    [401, "Invalid email or password", /match nahi hua/],
    [429, "Account locked. Try again in 600 seconds.", /10 minute baad/],
    [403, "Account is inactive", /WhatsApp/],
    [422, "value is not a valid email address", /naam@gmail.com/],
  ])("%i → Hinglish with the next step", (status, serverSays, want) => {
    const out = loginErrorHi(new ApiError(status, serverSays));
    expect(out).toMatch(want);
    expect(out).not.toMatch(ENGLISH);
  });
  it("a network failure keeps the client's own Hinglish line", () => {
    expect(loginErrorHi(new ApiError(0, NETWORK_TROUBLE_HI))).toBe(NETWORK_TROUBLE_HI);
  });
  it("a lock with no number never invents one", () => {
    expect(loginErrorHi(new ApiError(429, "locked"))).toMatch(/thodi der baad/);
  });
});

describe("signup errors", () => {
  it("an email already in use says: log in instead — and never echoes the address", () => {
    const out = registerErrorHi(new ApiError(409, "Email already registered: someone@example.com"));
    expect(out).toMatch(/Login karo/);
    expect(out).not.toContain("someone@example.com");
  });
  it("a weak password lists exactly what is missing, in Hinglish", () => {
    const out = registerErrorHi(new ApiError(400, "Weak password: at least one digit; at least one special character"));
    expect(out).toMatch(/ek ank \(0-9\)/);
    expect(out).toMatch(/ek nishaan/);
    expect(out).not.toMatch(ENGLISH);
  });
});

describe("the register form shows the server's password rules up front", () => {
  it("a password that passes every rule the server checks passes every line on the form", () => {
    expect(PASSWORD_RULES.every((r) => r.test("Bazaar#2026"))).toBe(true);
    expect(PASSWORD_RULES.filter((r) => !r.test("bazaar2026")).map((r) => r.key)).toEqual(["upper", "symbol"]);
  });
});
