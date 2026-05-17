import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  hasAcknowledgedPreTrade,
  PreTradeRiskModal,
} from "@/components/compliance/PreTradeRiskModal";
import {
  LS_KEY_PRE_TRADE_ACK,
  PRE_TRADE_COPY,
} from "@/lib/compliance/disclaimer-text";

describe("PreTradeRiskModal", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  it("does NOT render when open=false", () => {
    render(
      <PreTradeRiskModal open={false} onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.queryByTestId("pre-trade-risk-modal")).not.toBeInTheDocument();
  });

  it("renders title, intro, bullets, and both CTA buttons when open=true", () => {
    render(
      <PreTradeRiskModal
        open
        lang="en"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByTestId("pre-trade-risk-modal")).toBeInTheDocument();
    expect(screen.getByTestId("pre-trade-modal-title")).toHaveTextContent(
      PRE_TRADE_COPY.title_en,
    );
    expect(screen.getByTestId("pre-trade-modal-intro")).toHaveTextContent(
      PRE_TRADE_COPY.intro_en,
    );
    expect(screen.getByTestId("pre-trade-modal-cancel")).toBeInTheDocument();
    expect(screen.getByTestId("pre-trade-modal-confirm")).toBeInTheDocument();
  });

  it("renders all 5 bullets", () => {
    render(
      <PreTradeRiskModal
        open
        lang="en"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const bullets = screen.getByTestId("pre-trade-modal-bullets");
    for (const text of PRE_TRADE_COPY.bullets_en) {
      expect(bullets).toHaveTextContent(text);
    }
  });

  it("clicking Confirm fires onConfirm AND persists ack to localStorage", () => {
    const onConfirm = vi.fn();
    render(
      <PreTradeRiskModal open onConfirm={onConfirm} onCancel={vi.fn()} />,
    );
    expect(window.localStorage.getItem(LS_KEY_PRE_TRADE_ACK)).toBeNull();
    fireEvent.click(screen.getByTestId("pre-trade-modal-confirm"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem(LS_KEY_PRE_TRADE_ACK)).not.toBeNull();
  });

  it("clicking Cancel fires onCancel WITHOUT persisting ack", () => {
    const onCancel = vi.fn();
    render(<PreTradeRiskModal open onConfirm={vi.fn()} onCancel={onCancel} />);
    fireEvent.click(screen.getByTestId("pre-trade-modal-cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem(LS_KEY_PRE_TRADE_ACK)).toBeNull();
  });

  it("once acked, the modal does NOT render even with open=true (first-time-only contract)", () => {
    window.localStorage.setItem(LS_KEY_PRE_TRADE_ACK, new Date().toISOString());
    const onConfirm = vi.fn();
    render(
      <PreTradeRiskModal open onConfirm={onConfirm} onCancel={vi.fn()} />,
    );
    expect(screen.queryByTestId("pre-trade-risk-modal")).not.toBeInTheDocument();
  });

  it("hasAcknowledgedPreTrade reflects the localStorage stamp", () => {
    expect(hasAcknowledgedPreTrade()).toBe(false);
    window.localStorage.setItem(LS_KEY_PRE_TRADE_ACK, "2026-05-17T18:00:00Z");
    expect(hasAcknowledgedPreTrade()).toBe(true);
  });

  it("renders Hindi copy when lang='hi'", () => {
    render(
      <PreTradeRiskModal
        open
        lang="hi"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const modal = screen.getByTestId("pre-trade-risk-modal");
    expect(modal).toHaveAttribute("data-lang", "hi");
    expect(screen.getByTestId("pre-trade-modal-confirm")).toHaveTextContent(
      PRE_TRADE_COPY.cta_hi,
    );
  });
});
