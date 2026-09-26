/**
 * A 402 PLAN_REQUIRED (or any structured ``detail`` body) must reach callers
 * as a string message — the builders render ``err.detail`` directly, and an
 * object there throws "Objects are not valid as a React child".
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, ApiError, REQUEST_FAILED_HI, SERVER_TROUBLE_HI } from "@/shared/api/client";

beforeEach(() => {
  localStorage.setItem("tb_access_token", "t");
});

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })),
  );
}

async function capture(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p;
  } catch (e) {
    return e as ApiError;
  }
  throw new Error("expected rejection");
}

describe("ApiError.detail flattening", () => {
  it("402 with {code,message,upgrade_url} → detail is the message, data keeps the body", async () => {
    mockFetch(402, {
      detail: { code: "PLAN_REQUIRED", message: "Aapke plan mein 1 strategy ki limit hai (1 banayi hui).", upgrade_url: "/pricing", limit: 1, used: 1 },
    });
    const err = await capture(api.post("/strategies", {}));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(402);
    expect(err.detail).toBe("Aapke plan mein 1 strategy ki limit hai (1 banayi hui).");
    expect((err.data as { detail: { code: string } }).detail.code).toBe("PLAN_REQUIRED");
  });
  it("a plain string detail is unchanged", async () => {
    mockFetch(400, { detail: "'name' is required." });
    const err = await capture(api.post("/users/me/strategies", {}));
    expect(err.detail).toBe("'name' is required.");
  });
  // FLIPPED 2026-09-26 (guided-path walk): this test used to pin the fallback as "HTTP 500" —
  // a status code shown to a customer. Original expectation kept for the record:
  //   it("no detail at all falls back to HTTP <status>") … expect(err.detail).toBe("HTTP 500");
  it("no detail at all (or the middleware's scrubbed 'internal error') is plain words, never a code", async () => {
    mockFetch(500, {});
    const err = await api.get("/x").catch((e) => e);
    expect(err.detail).toBe(SERVER_TROUBLE_HI);
    mockFetch(503, { detail: "internal error", request_id: "abc" });
    const err2 = await api.get("/x").catch((e) => e);
    expect(err2.detail).toBe(SERVER_TROUBLE_HI);
    expect(err2.status).toBe(503);
    mockFetch(400, {});
    const err3 = await api.get("/x").catch((e) => e);
    expect(err3.detail).toBe(REQUEST_FAILED_HI);
    expect(err3.detail).not.toMatch(/\d{3}/);
  });
});
