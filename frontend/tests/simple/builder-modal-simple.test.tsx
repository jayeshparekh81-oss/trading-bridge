/** The builder's level-picker modal is Pro vocabulary — never shown in Simple mode. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const ladder = { ready: true, level: 1 as number };
vi.mock("@/hooks/useLadder", () => ({ useLadderOptional: () => ladder }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/strategies/new/beginner" }));

import { BuilderOnboardingModal } from "@/components/strategies/builder-onboarding-modal";

beforeEach(() => window.localStorage.clear());

describe("BuilderOnboardingModal in Simple vs Pro", () => {
  it("stays closed in Simple mode (level < 4)", async () => {
    ladder.level = 1;
    render(<BuilderOnboardingModal />);
    await new Promise((r) => setTimeout(r, 100));
    expect(screen.queryByText(/Welcome to Strategy Builder/)).toBeNull();
  });
  it("still opens for a Pro customer who has not seen it", async () => {
    ladder.level = 4;
    render(<BuilderOnboardingModal />);
    await waitFor(() => expect(screen.getByText(/Welcome to Strategy Builder/)).toBeInTheDocument());
  });
});
