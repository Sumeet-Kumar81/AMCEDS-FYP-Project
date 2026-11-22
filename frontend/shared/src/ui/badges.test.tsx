// UI kit rules (SDS §7.6, B1-A3-02): severity colour + text, confidence threshold (TC-08), trust,
// AI label, approximate ETA, 1122 notice.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Severity } from "../api/endpoints";
import { I18nProvider } from "../i18n/i18n";
import {
  AiRecommendationLabel,
  ApproximateEtaTag,
  CallNotice,
  ConfidenceMeter,
  SeverityBadge,
  TrustBadge,
} from "./badges";

describe("SeverityBadge", () => {
  it.each<[Severity, string, string]>([
    ["critical", "am-sev-critical", "Critical"],
    ["high", "am-sev-high", "High"],
    ["medium", "am-sev-medium", "Medium"],
    ["low", "am-sev-low", "Low"],
  ])("%s has its own colour class and visible text", (severity, cls, text) => {
    const { container } = render(<SeverityBadge severity={severity} />);
    const badge = container.firstElementChild!;
    expect(badge).toHaveClass("am-badge", cls);
    expect(badge).toHaveTextContent(text); // colour is never the only cue
  });

  it("no severity says so instead of guessing", () => {
    render(<SeverityBadge severity={null} />);
    expect(screen.getByText(/Severity unknown/)).toHaveClass("am-sev-unknown");
  });

  it("is translated to Urdu", () => {
    render(<I18nProvider initialLang="ur"><SeverityBadge severity="critical" /></I18nProvider>);
    expect(screen.getByText(/انتہائی سنگین/)).toBeInTheDocument();
  });
});

describe("ConfidenceMeter", () => {
  it("shows the percentage and no warning at or above the threshold", () => {
    render(<ConfidenceMeter value={0.6} />);
    expect(screen.getByText("Confidence: 60%")).toBeInTheDocument();
    expect(screen.queryByText("Dispatcher must check")).not.toBeInTheDocument();
  });

  it("below the threshold says the dispatcher must check (TC-08)", () => {
    render(<ConfidenceMeter value={0.59} />);
    expect(screen.getByText("Confidence: 59%")).toBeInTheDocument();
    expect(screen.getByText("Dispatcher must check")).toBeInTheDocument();
  });

  it("uses the incident's own threshold when given", () => {
    render(<ConfidenceMeter value={0.7} threshold={0.75} label="Type" />);
    expect(screen.getByText("Type: 70%")).toBeInTheDocument();
    expect(screen.getByText("Dispatcher must check")).toBeInTheDocument();
  });

  it("no value is never shown as confident", () => {
    render(<ConfidenceMeter value={null} />);
    expect(screen.getByText(/no confidence given/)).toBeInTheDocument();
    expect(screen.getByText("Dispatcher must check")).toBeInTheDocument();
  });

  it("keeps odd values inside 0–100 %", () => {
    render(<ConfidenceMeter value={1.4} />);
    expect(screen.getByText("Confidence: 100%")).toBeInTheDocument();
  });
});

describe("TrustBadge", () => {
  it("shows tier and score", () => {
    render(<TrustBadge tier="medium" score={60} />);
    expect(screen.getByText("Trust: Medium (60)")).toHaveClass("am-trust-medium");
  });

  it("a report without a trust result says so", () => {
    render(<TrustBadge tier={null} />);
    expect(screen.getByText("Trust: not scored yet")).toBeInTheDocument();
  });
});

describe("labels", () => {
  it("AI output is labelled as a recommendation", () => {
    render(<AiRecommendationLabel />);
    expect(screen.getByText(/AI recommendation — dispatcher decides/)).toBeInTheDocument();
  });

  it("approximate ETA is tagged, exact ETA is not", () => {
    const { rerender } = render(<ApproximateEtaTag approximate />);
    expect(screen.getByText(/Approximate/)).toBeInTheDocument();
    rerender(<ApproximateEtaTag approximate={false} />);
    expect(screen.queryByText(/Approximate/)).not.toBeInTheDocument();
  });

  it("the 1122 notice is shown in both languages (TC-47)", () => {
    const { unmount } = render(<CallNotice />);
    expect(screen.getByRole("note")).toHaveTextContent("If life is in danger, also call 1122.");
    unmount();
    render(<I18nProvider initialLang="ur"><CallNotice /></I18nProvider>);
    expect(screen.getByRole("note")).toHaveTextContent("1122 پر بھی کال کریں");
  });
});
