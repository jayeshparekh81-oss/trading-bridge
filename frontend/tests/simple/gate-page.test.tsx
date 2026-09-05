/** C9: the friendly gate — never a redirect, always a way home and a way to Pro. */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GatePage } from "@/components/simple/gate-page";

describe("GatePage", () => {
  it("offers Ghar and Pro, in the customer's words", () => {
    render(<GatePage lang="hinglish" needed={4} level={1} />);
    expect(screen.getByTestId("level-gate")).toHaveTextContent("Yeh aage khulega");
    expect(screen.getByTestId("gate-home")).toHaveAttribute("href", "/");
    expect(screen.getByTestId("gate-pro")).toHaveAttribute("href", "/settings#mode");
  });
  it("renders in Gujarati too", () => {
    render(<GatePage lang="gu" needed={2} level={1} />);
    expect(screen.getByTestId("level-gate").textContent).toMatch(/[઀-૿]/);
  });
});
