// Incident queue and read-only review (B1-A3-06, B1-A3-07 part): order and cards, flags, refresh every
// 5 s and pause when hidden, new-critical highlight, every AI value with its confidence, trust reasons,
// vehicles with plates and the approximate tag, no dispatch possible, 404/errors, roles.
// Fake backend; all data SIMULATED.
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { focusManager, QueryClient } from "@tanstack/react-query";
import { ApiClient, type IncidentDetailOut, type IncidentSummaryOut } from "@amceds/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Root } from "../App";

const NOW = new Date();
const ago = (min: number) => new Date(NOW.getTime() - min * 60_000).toISOString();

function card(id: number, extra: Partial<IncidentSummaryOut> = {}): IncidentSummaryOut {
  return {
    incident_id: id, reference_no: `INC-${String(id).padStart(6, "0")}`, channel: "web", received_at: ago(5),
    language: "Roman Urdu", location: { lat: 27.7052, lon: 68.8574, text: "near Clock Tower", source: "gps" },
    incident_type: "accident", severity: "high", victims_estimate: 3, confidence: 0.88, trust_score: 60,
    trust_tier: "medium", group_id: null, status: "triaged", review_reasons: [], ...extra,
  };
}

function detail(id: number, extra: Partial<IncidentDetailOut> = {}): IncidentDetailOut {
  return {
    ...card(id),
    original_text: "SIMULATED: Clock Tower ke paas bus accident hua hai, 3 log zakhmi",
    audio_ref: null, reporter_name: "SIMULATED Ali",
    ai_details: { triage: { incident_type: "accident", type_confidence: 0.93, severity: "high", severity_confidence: 0.55,
      victims_estimate: 3, victims_confidence: 0.7, language: "Roman Urdu", language_confidence: 0.9, missing_fields: [] } },
    trust_signals: [{ code: "real_details", points: 10, detail: "the message names a place, an event or people hurt" }],
    allocation_summary: { needed: { ambulance: 1 }, shortage: null, victims_unknown_check: false, routing_mode: "straight_line" },
    duplicate_candidates: [],
    recommendations: [
      { rec_id: 1, vehicle_id: 3, rank: 1, eta_seconds: 72, distance_meters: 802, created_at: ago(4), vehicle_type: "ambulance",
        eta_is_approximate: true, is_spare: false, route_geometry: null, batch_no: 1, is_current: true, plate_number: "SIM-AMB-03" },
      { rec_id: 2, vehicle_id: 1, rank: 2, eta_seconds: 81, distance_meters: 903, created_at: ago(4), vehicle_type: "ambulance",
        eta_is_approximate: true, is_spare: true, route_geometry: null, batch_no: 1, is_current: true, plate_number: "SIM-AMB-01" },
    ],
    assignments: [], dispatcher_decision: null, ...extra,
  };
}

function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), { status });
}

function backend(state: { list: IncidentSummaryOut[] | Response; details?: Record<number, IncidentDetailOut>; role?: string }) {
  const calls: string[] = [];
  const fetchFn = (async (input: RequestInfo | URL) => {
    const path = String(input).replace("http://api.test", "");
    calls.push(path);
    if (path === "/health") return json(200, { api: "ok", database: "ok" });
    if (path === "/api/v1/auth/login") return json(200, { access_token: "SIM-a", token_type: "bearer", expires_in: 900, refresh_token: "SIM-r" });
    if (path === "/api/v1/auth/me") {
      return json(200, { user_id: 2, full_name: "SIMULATED Dispatcher", username: "dispatcher1", role: state.role ?? "dispatcher", phone: null, on_duty: false });
    }
    if (path.startsWith("/api/v1/incidents?") || path === "/api/v1/incidents") {
      return state.list instanceof Response ? state.list.clone() : json(200, state.list);
    }
    const m = path.match(/^\/api\/v1\/incidents\/(\d+)$/);
    if (m) {
      const d = state.details?.[Number(m[1])];
      return d ? json(200, d) : json(404, { code: "not_found", message: "No such incident.", details: null });
    }
    return json(404, { code: "not_found", message: "no such path", details: null });
  }) as typeof fetch;
  return { client: new ApiClient({ baseUrl: "http://api.test", fetch: fetchFn }), calls, state };
}

function Where() {
  return <p data-testid="path">{useLocation().pathname}</p>;
}

async function openAs(b: ReturnType<typeof backend>, path = "/queue", user = userEvent.setup()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<MemoryRouter initialEntries={[path]}><Root client={b.client} queryClient={queryClient} /><Where /></MemoryRouter>);
  await user.type(screen.getByLabelText("Username"), "dispatcher1");
  await user.type(screen.getByLabelText("Password"), "SIM-pass");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  return user;
}

const listCalls = (b: ReturnType<typeof backend>) => b.calls.filter((c) => c.startsWith("/api/v1/incidents") && !/\/\d+$/.test(c)).length;

afterEach(() => {
  vi.useRealTimers();
  focusManager.setFocused(undefined);
});

describe("incident queue", () => {
  it("shows the cards in the server's order with severity, type, place, trust and flags", async () => {
    const b = backend({ list: [
      card(7, { severity: "critical", incident_type: "fire", review_reasons: ["vehicle_shortage"], received_at: ago(12) }),
      card(4, { severity: null, incident_type: null, status: "new", trust_tier: null, trust_score: null,
                location: { lat: null, lon: null, text: null, source: "unknown" }, review_reasons: ["location_unknown"] }),
      card(2, { severity: "low", status: "needs_check", trust_tier: "low", trust_score: 35, review_reasons: ["missing_info", "low_confidence"],
                location: { lat: null, lon: null, text: "Minara Road", source: "text" } }),
    ] });
    await openAs(b);
    const cards = await screen.findAllByTestId("incident-card");
    expect(cards.map((c) => c.getAttribute("data-incident"))).toEqual(["7", "4", "2"]);
    const [fire, fresh, low] = cards as [HTMLElement, HTMLElement, HTMLElement];
    expect(fire).toHaveTextContent("Critical");
    expect(fire).toHaveTextContent("Fire");
    expect(fire).toHaveTextContent("INC-000007");
    expect(fire).toHaveTextContent("12 min ago");
    expect(fire).toHaveTextContent("near Clock Tower · GPS 27.7052, 68.8574");
    expect(fire).toHaveTextContent("Trust: Medium (60)");
    expect(within(fire).getByText(/Not enough vehicles/)).toHaveClass("q-flag-urgent");
    expect(fresh).toHaveTextContent("Severity unknown");
    expect(fresh).toHaveTextContent("Type unknown");
    expect(fresh).toHaveTextContent("AI is reading this report…");
    expect(fresh).toHaveTextContent("Location unknown");
    expect(fresh).toHaveTextContent("Trust: not scored yet");
    expect(low).toHaveTextContent("More information needed");
    expect(low).toHaveTextContent("Low AI confidence — check");
    expect(low).toHaveTextContent("Minara Road");
    expect(screen.getByText("3 open reports")).toBeInTheDocument();
    expect(screen.getByTestId("updated")).toHaveTextContent(/^Updated /);
  });

  it("an unknown review reason is shown as its code, never hidden", async () => {
    await openAs(backend({ list: [card(1, { review_reasons: ["something_new"] })] }));
    expect(await screen.findByText(/something_new/)).toBeInTheDocument();
  });

  it("empty queue says so", async () => {
    await openAs(backend({ list: [] }));
    expect(await screen.findByText("No open reports right now.")).toBeInTheDocument();
  });

  it("a server error shows a message and a retry button", async () => {
    const b = backend({ list: json(500, { code: "internal_error", message: "SIMULATED failure", details: null }) });
    const user = await openAs(b);
    expect(await screen.findByRole("alert")).toHaveTextContent("SIMULATED failure");
    b.state.list = [card(1)];
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findAllByTestId("incident-card")).toHaveLength(1);
  });

  it("refreshes every 5 seconds and highlights a new critical report", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const b = backend({ list: [card(1)] });
    await openAs(b, "/queue", userEvent.setup({ advanceTimers: vi.advanceTimersByTime }));
    await screen.findAllByTestId("incident-card");
    expect(screen.queryByText(/new critical report/)).not.toBeInTheDocument();
    b.state.list = [card(9, { severity: "critical", incident_type: "fire" }), card(1)];
    await act(async () => { vi.advanceTimersByTime(5_100); });
    await waitFor(() => expect(screen.getAllByTestId("incident-card")).toHaveLength(2));
    expect(screen.getByText("🔴 1 new critical report(s)")).toBeInTheDocument();
    expect(screen.getAllByTestId("incident-card")[0]).toHaveClass("q-new-critical");
    expect(screen.getAllByTestId("incident-card")[1]).not.toHaveClass("q-new-critical");
  });

  it("does not refresh while the browser tab is hidden", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const b = backend({ list: [card(1)] });
    await openAs(b, "/queue", userEvent.setup({ advanceTimers: vi.advanceTimersByTime }));
    await screen.findAllByTestId("incident-card");
    const before = listCalls(b);
    act(() => focusManager.setFocused(false));
    await act(async () => { vi.advanceTimersByTime(30_000); });
    expect(listCalls(b)).toBe(before);
    act(() => focusManager.setFocused(true)); // back to the tab: fetched again
    await waitFor(() => expect(listCalls(b)).toBeGreaterThan(before));
  });

  it("a card opens the review screen", async () => {
    const b = backend({ list: [card(5)], details: { 5: detail(5) } });
    const user = await openAs(b);
    await user.click(await screen.findByTestId("incident-card"));
    expect(screen.getByTestId("path")).toHaveTextContent("/incidents/5");
    expect(await screen.findByRole("heading", { name: "INC-000005" })).toBeInTheDocument();
  });
});

describe("incident review (read-only)", () => {
  it("shows the report exactly as sent, reporter, place and channel", async () => {
    const urdu = "SIMULATED: مینارہ روڈ پر آگ لگ گئی ہے\nدوسری لائن";
    await openAs(backend({ list: [], details: { 5: detail(5, { original_text: urdu }) } }), "/incidents/5");
    const text = await screen.findByTestId("original-text");
    expect(text.textContent).toBe(urdu);
    expect(text).toHaveAttribute("dir", "auto");
    expect(screen.getByText("Reporter: SIMULATED Ali")).toBeInTheDocument();
    expect(screen.getByText(/via Web$/)).toBeInTheDocument();
    expect(screen.getByText(/near Clock Tower · GPS 27.7052, 68.8574/)).toBeInTheDocument();
  });

  it("every AI value has its confidence; a low one says the dispatcher must check", async () => {
    await openAs(backend({ list: [], details: { 5: detail(5) } }), "/incidents/5");
    const rows = await screen.findAllByTestId("ai-row");
    expect(rows.map((r) => r.querySelector("th")!.textContent)).toEqual(["Type", "Severity", "People hurt", "Language"]);
    expect(rows[0]).toHaveTextContent("Accident");
    expect(rows[0]).toHaveTextContent("Type: 93%");
    expect(rows[1]).toHaveTextContent("High");
    expect(rows[1]).toHaveTextContent("Severity: 55%");
    expect(rows[1]).toHaveTextContent("Dispatcher must check"); // 55 % < 60 %
    expect(rows[0]).not.toHaveTextContent("Dispatcher must check");
    expect(rows[2]).toHaveTextContent("3");
    expect(rows[3]).toHaveTextContent("Roman Urdu");
    expect(screen.getByText("Overall: 88%")).toBeInTheDocument();
    expect(screen.getAllByText(/AI recommendation — dispatcher decides/)).toHaveLength(2); // AI part and vehicles
  });

  it("shows each trust rule with its points and reason", async () => {
    await openAs(backend({ list: [], details: { 5: detail(5, { trust_signals: [
      { code: "real_details", points: 10, detail: "the message names a place, an event or people hurt" },
      { code: "vague", points: -15, detail: "the message is vague or joking" },
    ] }) } }), "/incidents/5");
    const signals = await screen.findAllByTestId("trust-signal");
    expect(signals.map((s) => s.textContent)).toEqual([
      "+10 the message names a place, an event or people hurt", "-15 the message is vague or joking"]);
    expect(screen.getByText("Every report starts at 50.")).toBeInTheDocument();
  });

  it("lists the recommended vehicles with plate, distance, ETA, the approximate tag and spares", async () => {
    await openAs(backend({ list: [], details: { 5: detail(5) } }), "/incidents/5");
    const rows = await screen.findAllByTestId("rec-row");
    expect(rows[0]).toHaveTextContent("1SIM-AMB-03Ambulance0.8 km1 min ≈ Approximate");
    expect(rows[1]).toHaveTextContent("SIM-AMB-01 (spare)");
    expect(screen.getByText("Needed: 1 × Ambulance")).toBeInTheDocument();
  });

  it("the review screen has the approval panel, and opening it sends nothing", async () => {
    const b = backend({ list: [], details: { 5: detail(5) } });
    await openAs(b, "/incidents/5");
    expect(await screen.findByRole("button", { name: "Approve dispatch" })).toBeInTheDocument();
    expect(b.calls.some((c) => c.includes("/dispatch"))).toBe(false);
  });

  it("shortage, unknown victims and the review reasons are spelled out", async () => {
    await openAs(backend({ list: [], details: { 5: detail(5, {
      review_reasons: ["vehicle_shortage", "low_trust_urgent"],
      allocation_summary: { needed: { ambulance: 2, fire_truck: 1 }, shortage: { ambulance: 1 }, victims_unknown_check: true },
    }) } }), "/incidents/5");
    expect(await screen.findByText("Not enough vehicles: 1 × Ambulance missing.")).toBeInTheDocument();
    expect(screen.getByText("Number of people hurt is not known: check before dispatching.")).toBeInTheDocument();
    expect(screen.getByText("Needed: 2 × Ambulance, 1 × Fire truck")).toBeInTheDocument();
    const reasons = screen.getByRole("heading", { name: "Why the dispatcher should look" }).parentElement!;
    expect(reasons).toHaveTextContent("Low trust — urgent, not held back");
  });

  it("an AI failure says manual mode and shows no AI values", async () => {
    await openAs(backend({ list: [], details: { 5: detail(5, { ai_details: null, review_reasons: ["ai_failed"], status: "needs_check",
      incident_type: null, severity: null, confidence: null, recommendations: [], allocation_summary: null }) } }), "/incidents/5");
    expect(await screen.findByText(/The AI could not read this report\. Decide by hand \(manual mode\)/)).toBeInTheDocument();
    expect(screen.queryAllByTestId("ai-row")).toHaveLength(0);
    expect(screen.getByText(/No vehicle could be recommended/)).toBeInTheDocument();
  });

  it("a new report says the AI is still reading", async () => {
    await openAs(backend({ list: [], details: { 5: detail(5, { status: "new", ai_details: null, recommendations: [] }) } }), "/incidents/5");
    expect(await screen.findAllByText("⏳ AI is reading this report…")).not.toHaveLength(0);
  });

  it("an unknown incident says so; a non-number id is not even requested", async () => {
    const b = backend({ list: [], details: {} });
    await openAs(b, "/incidents/404");
    expect(await screen.findByText("There is no incident with this number.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Back to the queue" })).toBeInTheDocument();
  });

  it("a bad id in the address shows not found without calling the server", async () => {
    const b = backend({ list: [], details: {} });
    await openAs(b, "/incidents/abc");
    expect(await screen.findByText("There is no incident with this number.")).toBeInTheDocument();
    expect(b.calls.some((c) => c.startsWith("/api/v1/incidents/"))).toBe(false);
  });

  it("only dispatchers may open it", async () => {
    await openAs(backend({ list: [], details: { 5: detail(5) }, role: "admin" }), "/incidents/5");
    expect(await screen.findByRole("heading", { name: "Not allowed" })).toBeInTheDocument();
  });
});
