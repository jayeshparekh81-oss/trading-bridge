import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  LangToggle,
  LS_KEY_LANG,
  readLang,
  writeLang,
} from "@/components/help/LangToggle";

describe("LangToggle", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  it("renders both buttons with aria-pressed reflecting `lang`", () => {
    const onChange = vi.fn();
    render(<LangToggle lang="hi" onChange={onChange} />);
    expect(screen.getByTestId("help-lang-en")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("help-lang-hi")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("clicking 'English' fires onChange('en')", () => {
    const onChange = vi.fn();
    render(<LangToggle lang="hi" onChange={onChange} />);
    fireEvent.click(screen.getByTestId("help-lang-en"));
    expect(onChange).toHaveBeenCalledWith("en");
  });

  it("clicking 'हिंदी' fires onChange('hi')", () => {
    const onChange = vi.fn();
    render(<LangToggle lang="en" onChange={onChange} />);
    fireEvent.click(screen.getByTestId("help-lang-hi"));
    expect(onChange).toHaveBeenCalledWith("hi");
  });

  it("writeLang persists to localStorage", () => {
    writeLang("en");
    expect(window.localStorage.getItem(LS_KEY_LANG)).toBe("en");
    writeLang("hi");
    expect(window.localStorage.getItem(LS_KEY_LANG)).toBe("hi");
  });

  it("readLang returns the persisted value", () => {
    window.localStorage.setItem(LS_KEY_LANG, "en");
    expect(readLang()).toBe("en");
    window.localStorage.setItem(LS_KEY_LANG, "hi");
    expect(readLang()).toBe("hi");
  });

  it("readLang falls back to 'hi' when key missing or invalid", () => {
    expect(readLang()).toBe("hi");
    window.localStorage.setItem(LS_KEY_LANG, "fr");
    expect(readLang()).toBe("hi");
  });
});
