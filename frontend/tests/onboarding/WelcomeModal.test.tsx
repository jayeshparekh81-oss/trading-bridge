import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WelcomeModal } from "@/components/onboarding/WelcomeModal";

describe("WelcomeModal", () => {
  function renderModal(overrides: Partial<React.ComponentProps<typeof WelcomeModal>> = {}) {
    const onStart = vi.fn();
    const onLater = vi.fn();
    const onLangChange = vi.fn();
    render(
      <WelcomeModal
        userName="Jayesh"
        lang="hi"
        onLangChange={onLangChange}
        onStart={onStart}
        onLater={onLater}
        {...overrides}
      />,
    );
    return { onStart, onLater, onLangChange };
  }

  it("renders the Namaste greeting with the user's name", () => {
    renderModal({ userName: "Jayesh", lang: "hi" });
    expect(screen.getByTestId("onboarding-welcome-title")).toHaveTextContent(
      /namaste jayesh/i,
    );
    expect(screen.getByTestId("onboarding-welcome-badge")).toHaveTextContent(
      /l&t engineer built/i,
    );
  });

  it("language toggle switches en ↔ hi via onLangChange", () => {
    const { onLangChange } = renderModal({ lang: "hi" });
    fireEvent.click(screen.getByTestId("onboarding-lang-en"));
    expect(onLangChange).toHaveBeenCalledWith("en");
    fireEvent.click(screen.getByTestId("onboarding-lang-hi"));
    expect(onLangChange).toHaveBeenLastCalledWith("hi");
  });

  it("renders English copy when lang='en'", () => {
    renderModal({ lang: "en", userName: "Jayesh" });
    expect(screen.getByTestId("onboarding-welcome-title")).toHaveTextContent(
      /welcome to tradetri, jayesh/i,
    );
    expect(screen.getByTestId("onboarding-welcome-start")).toHaveTextContent(
      /start tour/i,
    );
  });

  it("'Baad mein' button fires onLater (skip path)", () => {
    const { onLater, onStart } = renderModal({ lang: "hi" });
    fireEvent.click(screen.getByTestId("onboarding-welcome-later"));
    expect(onLater).toHaveBeenCalledTimes(1);
    expect(onStart).not.toHaveBeenCalled();
  });

  it("'Tour shuru karo' button fires onStart (launches tour)", () => {
    const { onStart, onLater } = renderModal({ lang: "hi" });
    fireEvent.click(screen.getByTestId("onboarding-welcome-start"));
    expect(onStart).toHaveBeenCalledTimes(1);
    expect(onLater).not.toHaveBeenCalled();
  });
});
