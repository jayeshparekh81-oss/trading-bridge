import { act, fireEvent, render, screen } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

// ── next/navigation ───────────────────────────────────────────────────
// usePathname / useRouter need stable jsdom-safe stubs. Modules importing
// these from "next/navigation" otherwise throw because vitest doesn't
// boot a Next runtime.
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: pushMock, replace: pushMock }),
}));

// ── next/dynamic + react-joyride ──────────────────────────────────────
// Replace the dynamic-loaded Joyride with a synchronous stub that
// captures the orchestrator's `callback` prop. We mock `next/dynamic`
// itself (rather than the joyride module) because the orchestrator's
// import goes through `dynamic(() => import("react-joyride"))` — any
// joyride mock has to flow through the dynamic loader, and in jsdom the
// async loader resolution races the test assertions.
const joyrideCaptured: { lastCallback: ((data: unknown) => void) | null } = {
  lastCallback: null,
};

function JoyrideStub(props: {
  callback?: (data: unknown) => void;
  steps: unknown[];
}) {
  joyrideCaptured.lastCallback = props.callback ?? null;
  return (
    <div
      data-testid="joyride-stub"
      data-step-count={props.steps.length}
    />
  );
}

vi.mock("next/dynamic", () => ({
  // Production behaviour: `dynamic(loader, opts)` returns a component
  // that swaps in the loader's resolved default at runtime. We just
  // return the stub directly — the orchestrator has only one dynamic()
  // call in scope of this test, and it always targets joyride.
  default: () => JoyrideStub,
}));

import { OnboardingTour } from "@/components/onboarding/OnboardingTour";
import {
  LS_KEY_COMPLETED,
  LS_KEY_SKIPPED,
  RESTART_EVENT,
} from "@/hooks/useOnboarding";
import { TOUR_STEPS } from "@/lib/onboarding/tourSteps";

async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

describe("OnboardingTour", () => {
  beforeEach(() => {
    pushMock.mockReset();
    joyrideCaptured.lastCallback = null;
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("does NOT render the welcome modal when the tour has already been completed", async () => {
    window.localStorage.setItem(LS_KEY_COMPLETED, "true");
    render(<OnboardingTour userName="Jayesh" />);
    await flush();
    expect(
      screen.queryByTestId("onboarding-welcome-modal"),
    ).not.toBeInTheDocument();
  });

  it("shows the welcome modal on first mount when no flags are set", async () => {
    render(<OnboardingTour userName="Jayesh" />);
    await flush();
    expect(
      screen.getByTestId("onboarding-welcome-modal"),
    ).toBeInTheDocument();
  });

  it("'Later' button sets the skipped flag and hides the modal", async () => {
    render(<OnboardingTour userName="Jayesh" />);
    await flush();
    fireEvent.click(screen.getByTestId("onboarding-welcome-later"));
    expect(window.localStorage.getItem(LS_KEY_SKIPPED)).toBe("true");
    expect(
      screen.queryByTestId("onboarding-welcome-modal"),
    ).not.toBeInTheDocument();
  });

  it("'Tour shuru' transitions from welcome to the joyride stage with all 5 steps", async () => {
    render(<OnboardingTour userName="Jayesh" />);
    await flush();
    fireEvent.click(screen.getByTestId("onboarding-welcome-start"));
    await flush();
    const stub = await screen.findByTestId("joyride-stub");
    expect(stub).toHaveAttribute(
      "data-step-count",
      String(TOUR_STEPS.length),
    );
    expect(TOUR_STEPS).toHaveLength(5);
  });

  it("joyride 'skipped' callback sets the completed flag (no success screen)", async () => {
    render(<OnboardingTour userName="Jayesh" />);
    await flush();
    fireEvent.click(screen.getByTestId("onboarding-welcome-start"));
    await flush();
    expect(joyrideCaptured.lastCallback).not.toBeNull();
    await act(async () => {
      joyrideCaptured.lastCallback?.({ status: "skipped" });
    });
    expect(window.localStorage.getItem(LS_KEY_COMPLETED)).toBe("true");
    expect(
      screen.queryByTestId("onboarding-success-modal"),
    ).not.toBeInTheDocument();
  });

  it("joyride 'finished' callback sets the completed flag AND shows the success screen", async () => {
    render(<OnboardingTour userName="Jayesh" />);
    await flush();
    fireEvent.click(screen.getByTestId("onboarding-welcome-start"));
    await flush();
    await act(async () => {
      joyrideCaptured.lastCallback?.({ status: "finished" });
    });
    expect(window.localStorage.getItem(LS_KEY_COMPLETED)).toBe("true");
    expect(
      screen.getByTestId("onboarding-success-modal"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("onboarding-success-title")).toHaveTextContent(
      /tour complete/i,
    );
  });

  it("success-screen 'Build a strategy' CTA routes to /strategies/new", async () => {
    render(<OnboardingTour userName="Jayesh" />);
    await flush();
    fireEvent.click(screen.getByTestId("onboarding-welcome-start"));
    await flush();
    await act(async () => {
      joyrideCaptured.lastCallback?.({ status: "finished" });
    });
    fireEvent.click(screen.getByTestId("onboarding-success-build"));
    expect(pushMock).toHaveBeenCalledWith("/strategies/new");
  });

  it("success-screen 'View chart' CTA routes to /chart", async () => {
    render(<OnboardingTour userName="Jayesh" />);
    await flush();
    fireEvent.click(screen.getByTestId("onboarding-welcome-start"));
    await flush();
    await act(async () => {
      joyrideCaptured.lastCallback?.({ status: "finished" });
    });
    fireEvent.click(screen.getByTestId("onboarding-success-chart"));
    expect(pushMock).toHaveBeenCalledWith("/chart");
  });

  it("dispatching the restart event re-arms the tour after completion", async () => {
    window.localStorage.setItem(LS_KEY_COMPLETED, "true");
    render(<OnboardingTour userName="Jayesh" />);
    await flush();
    expect(
      screen.queryByTestId("onboarding-welcome-modal"),
    ).not.toBeInTheDocument();
    await act(async () => {
      window.dispatchEvent(new CustomEvent(RESTART_EVENT));
    });
    expect(
      screen.getByTestId("onboarding-welcome-modal"),
    ).toBeInTheDocument();
    expect(window.localStorage.getItem(LS_KEY_COMPLETED)).toBeNull();
  });
});
