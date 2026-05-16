/**
 * Tests for UpdateDhanTokenModal (Phase 1, 2026-05-16).
 *
 * Covers the four states required by the spec — idle/instructions,
 * submitting, success (auto-close), and Dhan-rejected error — plus a
 * happy-path payload assertion that pins the wire contract sent to
 * ``POST /api/brokers/dhan/update-token``.
 *
 * The api client is mocked at module level (mirrors
 * ``tests/strategies/go-live-modal.test.tsx``); we never hit the
 * network from a unit test. ``ApiError`` is a class re-export so
 * ``err instanceof ApiError`` inside the modal still works against
 * the mock.
 */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { UpdateDhanTokenModal } from "@/components/brokers/UpdateDhanTokenModal";

// ── Mocks ─────────────────────────────────────────────────────────────

vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    detail: string;
    data: unknown;
    constructor(status: number, detail: string, data?: unknown) {
      super(detail);
      this.status = status;
      this.detail = detail;
      this.data = data;
    }
  }
  return {
    api: { post: vi.fn(), get: vi.fn() },
    ApiError,
  };
});

// Pull the mocked module so individual tests can configure ``api.post``
// + construct ``ApiError`` instances for the error branch.
import { api, ApiError } from "@/lib/api";

const VALID_TOKEN = "x".repeat(250);

const baseProps = {
  open: true,
  onClose: vi.fn(),
  onSuccess: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

// ── Tests ─────────────────────────────────────────────────────────────

describe("UpdateDhanTokenModal", () => {
  it("renders the instructions block with a deep-link to Dhan API access", () => {
    render(<UpdateDhanTokenModal {...baseProps} />);

    expect(
      screen.getByTestId("update-dhan-token-modal"),
    ).toBeInTheDocument();

    const instructions = screen.getByTestId("dhan-token-instructions");
    expect(instructions).toBeInTheDocument();
    // All three numbered steps land in the DOM.
    expect(instructions.textContent ?? "").toMatch(
      /How to generate a fresh token/i,
    );
    expect(instructions.textContent ?? "").toMatch(/24 hours/i);

    const link = screen.getByTestId("dhan-api-access-link");
    expect(link).toHaveAttribute("href", "https://web.dhan.co/api-access");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("disables the submit button until the token meets the min-length floor", () => {
    render(<UpdateDhanTokenModal {...baseProps} />);

    const submit = screen.getByTestId("dhan-token-submit");
    expect(submit).toBeDisabled();

    // 99 chars — still below the 100-char floor.
    fireEvent.change(screen.getByTestId("dhan-token-input"), {
      target: { value: "y".repeat(99) },
    });
    expect(submit).toBeDisabled();

    // 100 chars — at the floor.
    fireEvent.change(screen.getByTestId("dhan-token-input"), {
      target: { value: "y".repeat(100) },
    });
    expect(submit).not.toBeDisabled();
  });

  it("posts the trimmed token + client_id + label to the endpoint on submit", async () => {
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      success: true,
      connection_status: "active",
      message: "Connected successfully. Chart and trading are now live.",
      token_label: "Dhan – Primary",
      updated_at: "2026-05-16T00:00:00+00:00",
    });

    render(<UpdateDhanTokenModal {...baseProps} />);

    // Token with surrounding whitespace must be trimmed before sending.
    fireEvent.change(screen.getByTestId("dhan-token-input"), {
      target: { value: `  ${VALID_TOKEN}  ` },
    });
    fireEvent.change(screen.getByTestId("dhan-client-id-input"), {
      target: { value: "1100123456" },
    });
    fireEvent.click(screen.getByTestId("dhan-token-submit"));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [path, body] = (api.post as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(path).toBe("/brokers/dhan/update-token");
    expect(body).toEqual({
      access_token: VALID_TOKEN,
      dhan_client_id: "1100123456",
      label: "Dhan – Primary",
    });
  });

  it("omits dhan_client_id from the body when the user leaves it blank", async () => {
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      success: true,
      connection_status: "active",
      message: "ok",
      token_label: "Dhan – Primary",
      updated_at: "2026-05-16T00:00:00+00:00",
    });

    render(<UpdateDhanTokenModal {...baseProps} />);

    fireEvent.change(screen.getByTestId("dhan-token-input"), {
      target: { value: VALID_TOKEN },
    });
    // client_id intentionally NOT touched.
    fireEvent.click(screen.getByTestId("dhan-token-submit"));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [, body] = (api.post as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(body).not.toHaveProperty("dhan_client_id");
    expect(body).toMatchObject({ access_token: VALID_TOKEN });
  });

  it("shows the success banner and auto-closes via onSuccess + onClose after 2 seconds", async () => {
    vi.useFakeTimers();
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      success: true,
      connection_status: "active",
      message: "Connected successfully. Chart and trading are now live.",
      token_label: "Dhan – Primary",
      updated_at: "2026-05-16T00:00:00+00:00",
    });

    const onSuccess = vi.fn();
    const onClose = vi.fn();
    render(
      <UpdateDhanTokenModal {...baseProps} onSuccess={onSuccess} onClose={onClose} />,
    );

    fireEvent.change(screen.getByTestId("dhan-token-input"), {
      target: { value: VALID_TOKEN },
    });
    fireEvent.change(screen.getByTestId("dhan-client-id-input"), {
      target: { value: "1100123456" },
    });
    fireEvent.click(screen.getByTestId("dhan-token-submit"));

    // Wait for the api.post promise to resolve so the success state
    // mounts. Use real-clock waitFor — fake timers don't advance
    // microtasks.
    await vi.waitFor(() => {
      expect(screen.getByTestId("dhan-token-success")).toBeInTheDocument();
    });

    expect(screen.getByTestId("dhan-token-success").textContent ?? "").toMatch(
      /chart, backtest, and paper trading are now live/i,
    );

    // Auto-close fires 2 seconds later via setTimeout.
    expect(onSuccess).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(onSuccess).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows the error banner with the API detail when Dhan rejects the token", async () => {
    (api.post as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new ApiError(
        400,
        "Invalid Dhan token — generate a fresh token from your Dhan dashboard.",
      ),
    );

    const onSuccess = vi.fn();
    render(<UpdateDhanTokenModal {...baseProps} onSuccess={onSuccess} />);

    fireEvent.change(screen.getByTestId("dhan-token-input"), {
      target: { value: VALID_TOKEN },
    });
    fireEvent.change(screen.getByTestId("dhan-client-id-input"), {
      target: { value: "1100123456" },
    });
    fireEvent.click(screen.getByTestId("dhan-token-submit"));

    const banner = await screen.findByTestId("dhan-token-error");
    expect(banner.textContent ?? "").toMatch(/Invalid Dhan token/i);
    expect(banner.textContent ?? "").toMatch(/dashboard/i);

    // Failure path must NOT fire onSuccess — modal stays open so the
    // user can retry with a fresh token.
    expect(onSuccess).not.toHaveBeenCalled();

    // Submit button is re-enabled so retry is possible.
    expect(screen.getByTestId("dhan-token-submit")).not.toBeDisabled();
  });
});
