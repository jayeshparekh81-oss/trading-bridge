import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FAQAccordion } from "@/components/help/FAQAccordion";
import type { FAQ } from "@/lib/help/faq-content";

function makeFaq(id: string): FAQ {
  return {
    id,
    category: "getting-started",
    question_en: `Q-${id}-en`,
    question_hi: `Q-${id}-hi`,
    answer_en: `A-${id}-en`,
    answer_hi: `A-${id}-hi`,
    tags: ["test"],
  };
}

describe("FAQAccordion", () => {
  it("renders empty message when faqs array is empty", () => {
    render(<FAQAccordion faqs={[]} lang="en" emptyMessage="nothing here" />);
    expect(screen.getByTestId("help-faq-empty")).toHaveTextContent(
      "nothing here",
    );
  });

  it("renders one FAQItem per FAQ", () => {
    const faqs = [makeFaq("a"), makeFaq("b"), makeFaq("c")];
    render(<FAQAccordion faqs={faqs} lang="en" />);
    expect(screen.getAllByTestId("help-faq-item")).toHaveLength(3);
  });

  it("items start collapsed (no answer rendered)", () => {
    const faqs = [makeFaq("a")];
    render(<FAQAccordion faqs={faqs} lang="en" />);
    expect(screen.queryByTestId("help-faq-answer")).not.toBeInTheDocument();
  });

  it("clicking a question expands the answer", () => {
    const faqs = [makeFaq("a")];
    render(<FAQAccordion faqs={faqs} lang="en" />);
    fireEvent.click(screen.getByTestId("help-faq-toggle"));
    expect(screen.getByTestId("help-faq-answer")).toHaveTextContent(
      "A-a-en",
    );
  });

  it("clicking again collapses the answer", () => {
    const faqs = [makeFaq("a")];
    render(<FAQAccordion faqs={faqs} lang="en" />);
    const toggle = screen.getByTestId("help-faq-toggle");
    fireEvent.click(toggle);
    fireEvent.click(toggle);
    expect(screen.queryByTestId("help-faq-answer")).not.toBeInTheDocument();
  });

  it("multiple items can be open simultaneously", () => {
    const faqs = [makeFaq("a"), makeFaq("b"), makeFaq("c")];
    render(<FAQAccordion faqs={faqs} lang="en" />);
    const toggles = screen.getAllByTestId("help-faq-toggle");
    fireEvent.click(toggles[0]);
    fireEvent.click(toggles[2]);
    const items = screen.getAllByTestId("help-faq-item");
    expect(items[0]).toHaveAttribute("data-faq-open", "true");
    expect(items[1]).toHaveAttribute("data-faq-open", "false");
    expect(items[2]).toHaveAttribute("data-faq-open", "true");
  });

  it("renders Hindi question + answer when lang='hi'", () => {
    const faqs = [makeFaq("a")];
    render(<FAQAccordion faqs={faqs} lang="hi" />);
    expect(screen.getByTestId("help-faq-toggle")).toHaveTextContent(
      "Q-a-hi",
    );
    fireEvent.click(screen.getByTestId("help-faq-toggle"));
    expect(screen.getByTestId("help-faq-answer")).toHaveTextContent(
      "A-a-hi",
    );
  });
});
