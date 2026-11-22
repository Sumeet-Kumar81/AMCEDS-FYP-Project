// Dispatch approval panel (B1-A3-08): three clicks for a recommended dispatch (NFR-P14), nothing sent
// without Confirm, preselection of what is needed, 409 → next best (TC-22), manual mode, honest success
// with the "inform the driver" instruction. Fake backend with the server's rules; data SIMULATED.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient } from "@tanstack/react-query";
import { ApiClient, type IncidentDetailOut, type VehicleOut } from "@amceds/shared";
import { describe, expect, it } from "vitest";
import { Root } from "../App";

const NOW = new Date().toISOString();

function vehicle(id: number, plate: string, extra: Partial<VehicleOut> = {}): VehicleOut {
  return { vehicle_id: id, plate_number: plate, vehicle_type: "ambulance", status: "available", station_name: null,
    patient_capacity: 2, driver_id: 100 + id, driver_name: `SIMULATED Driver ${id}`, driver_on_duty: true, lat: 27.7, lon: 68.85,
    last_seen_at: NOW, signal_lost: false, has_open_assignment: false, can_dispatch: true, distance_meters: 800 * id,
    distance_is_approximate: true, ...extra };
}

function rec(vid: number, rank: number, plate: string, extra: Record<string, unknown> = {}) {
  return { rec_id: rank, vehicle_id: vid, rank, eta_seconds: 60 * rank, distance_meters: 800 * rank, created_at: NOW,
    vehicle_type: "ambulance" as const, eta_is_approximate: true, is_spare: false, route_geometry: null, batch_no: 1,
    is_current: true, plate_number: plate, ...extra };
}

function incident(extra: Partial<IncidentDetailOut> = {}): IncidentDetailOut {
  return {
    incident_id: 1, reference_no: "INC-000001", channel: "web", received_at: NOW, language: "Roman Urdu",
    location: { lat: 27.71, lon: 68.85, text: null, source: "gps" }, incident_type: "accident", severity: "critical",
    victims_estimate: 5, confidence: 0.9, trust_score: 60, trust_tier: "medium", group_id: null, status: "triaged",
    review_reasons: [], original_text: "SIMULATED: Military Road par takkar, 5 log zakhmi", audio_ref: null,
    reporter_name: null, ai_details: null, trust_signals: [],
    allocation_summary: { needed: { ambulance: 1 }, shortage: null },
    duplicate_candidates: [],
    recommendations: [rec(5, 1, "SIM-AMB-03"), rec(1, 2, "SIM-AMB-01"), rec(2, 3, "SIM-AMB-02", { is_spare: true })],
    assignments: [], dispatcher_decision: null, ...extra,
  };
}

function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), { status });
}

type DispatchReply = Response | Error | (() => Promise<Response>);

/** A backend with one incident, a fleet and the real dispatch rules (or scripted replies). */
function backend(opts: { incident?: IncidentDetailOut; vehicles?: VehicleOut[]; replies?: DispatchReply[] } = {}) {
  let inc = opts.incident ?? incident();
  const fleet = opts.vehicles ?? [vehicle(5, "SIM-AMB-03"), vehicle(1, "SIM-AMB-01"), vehicle(2, "SIM-AMB-02"),
    vehicle(4, "SIM-BKP-01", { vehicle_type: "backup" })];
  const posts: { vehicle_ids: number[]; override_reason?: string | null }[] = [];
  const replies = opts.replies ?? [];
  const fetchFn = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const path = String(input).replace("http://api.test", "");
    if (path === "/health") return json(200, { api: "ok", database: "ok" });
    if (path === "/api/v1/auth/login") return json(200, { access_token: "SIM-a", token_type: "bearer", expires_in: 900, refresh_token: "SIM-r" });
    if (path === "/api/v1/auth/me") return json(200, { user_id: 2, full_name: "SIMULATED Dispatcher", username: "dispatcher1", role: "dispatcher", phone: null, on_duty: false });
    if (path.startsWith("/api/v1/incidents?") || path === "/api/v1/incidents") return json(200, [inc]);
    if (path === "/api/v1/incidents/1") return json(200, inc);
    if (path.startsWith("/api/v1/vehicles")) return json(200, fleet);
    if (path === "/api/v1/incidents/1/dispatch") {
      const body = JSON.parse(String(init.body));
      posts.push(body);
      const scripted = replies.shift();
      if (scripted instanceof Error) throw scripted;
      if (typeof scripted === "function") return scripted();
      if (scripted) return scripted;
      const busy = body.vehicle_ids.filter((id: number) => fleet.find((v) => v.vehicle_id === id)?.has_open_assignment);
      if (busy.length) {
        const next = inc.recommendations!.map((r) => r.vehicle_id)
          .filter((id) => !body.vehicle_ids.includes(id) && fleet.find((v) => v.vehicle_id === id)?.can_dispatch);
        return json(409, { code: "vehicle_locked", message: "A chosen vehicle already has an open assignment.",
          details: { vehicle_ids: busy, next_best: next } });
      }
      const out = body.vehicle_ids.map((id: number, k: number) => ({ assignment_id: 50 + k, vehicle_id: id, approved_by: 2,
        hospital_id: null, status: "approved", approved_at: NOW }));
      for (const id of body.vehicle_ids) Object.assign(fleet.find((v) => v.vehicle_id === id)!, { has_open_assignment: true, can_dispatch: false, status: "assigned" });
      inc = { ...inc, status: "dispatched", assignments: [...(inc.assignments ?? []), ...out] };
      return json(201, out);
    }
    return json(404, { code: "not_found", message: "no such path", details: null });
  }) as typeof fetch;
  return { client: new ApiClient({ baseUrl: "http://api.test", fetch: fetchFn }), posts, fleet };
}

async function openIncident(b: ReturnType<typeof backend>) {
  const user = userEvent.setup();
  render(<MemoryRouter initialEntries={["/queue"]}><Root client={b.client} queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })} /></MemoryRouter>);
  await user.type(screen.getByLabelText("Username"), "dispatcher1");
  await user.type(screen.getByLabelText("Password"), "SIM-pass");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  return user;
}

const box = (plate: string) => screen.getByRole("checkbox", { name: `Send ${plate}` }) as HTMLInputElement;
/** The vehicle list has loaded (preticking happens then). Every fixture has SIM-BKP-01 outside the recommendations. */
async function ready() {
  await waitFor(() => expect(screen.getAllByTestId("other-row").length).toBeGreaterThan(0));
}

describe("three clicks for a recommended dispatch", () => {
  it("open incident → Approve → Confirm sends the preticked vehicle and says so honestly", async () => {
    const b = backend();
    const user = await openIncident(b);
    let clicks = 0;
    const click = async (el: Element) => { clicks++; await user.click(el); };
    await click(await screen.findByTestId("incident-card"));          // 1
    await ready();
    await click(screen.getByRole("button", { name: "Approve dispatch" })); // 2
    const dialog = screen.getByRole("dialog", { name: "Confirm dispatch" });
    expect(within(dialog).getByTestId("summary-vehicles")).toHaveTextContent("SIM-AMB-03 — Ambulance");
    await click(within(dialog).getByRole("button", { name: "Confirm" })); // 3
    expect(await screen.findByText("✔ Dispatched: SIM-AMB-03.")).toBeInTheDocument();
    expect(screen.getByText(/The driver is not alerted automatically yet — inform the driver by radio or phone\./)).toBeInTheDocument();
    expect(clicks).toBe(3);
    expect(b.posts).toEqual([{ vehicle_ids: [5], override_reason: null }]);
    expect(await screen.findByTestId("assignments")).toHaveTextContent("SIM-AMB-03 — approved");
    expect(screen.getByTestId("assignments")).toHaveTextContent("by you");
    await waitFor(() => expect(screen.getByRole("heading", { name: "INC-000001" }).parentElement).toHaveTextContent("Dispatched"));
  });
});

describe("nothing is sent without Confirm", () => {
  it("Cancel and Escape close the summary without a request", async () => {
    const b = backend();
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(b.posts).toHaveLength(0);
  });

  it("pressing Confirm twice at once sends one request", async () => {
    let release!: (r: Response) => void;
    const b = backend({ replies: [() => new Promise<Response>((r) => { release = r; })] });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    const confirm = screen.getByRole("button", { name: "Confirm" });
    act(() => { fireEvent.click(confirm); fireEvent.click(confirm); });
    await waitFor(() => expect(b.posts).toHaveLength(1));
    await act(async () => release(json(201, [{ assignment_id: 9, vehicle_id: 5, approved_by: 2, hospital_id: null, status: "approved", approved_at: NOW }])));
    await screen.findByText("✔ Dispatched: SIM-AMB-03.");
    expect(b.posts).toHaveLength(1);
  });

  it("a network failure is never shown as success", async () => {
    const b = backend({ replies: [new TypeError("Failed to fetch")] });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByTestId("dispatch-problem")).toHaveTextContent("Not sent: Could not reach the server.");
    expect(screen.queryByText(/Dispatched:/)).not.toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument(); // the dispatcher can try again
  });
});

describe("what is preticked", () => {
  it("the needed vehicles are ticked, spares are not, and busy ones are skipped with the reason", async () => {
    const b = backend({ vehicles: [vehicle(5, "SIM-AMB-03", { has_open_assignment: true, can_dispatch: false, status: "assigned" }),
      vehicle(1, "SIM-AMB-01"), vehicle(2, "SIM-AMB-02"), vehicle(4, "SIM-BKP-01", { vehicle_type: "backup" })] });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    expect(box("SIM-AMB-03").checked).toBe(false);
    expect(box("SIM-AMB-03")).toBeDisabled();
    expect(screen.getAllByTestId("rec-row")[0]).toHaveTextContent("not available now: already on another job");
    expect(box("SIM-AMB-01").checked).toBe(true);  // the next needed one instead
    expect(box("SIM-AMB-02").checked).toBe(false); // spare
  });

  it("when two are needed, a spare in between is skipped", async () => {
    const b = backend({ incident: incident({ allocation_summary: { needed: { ambulance: 2 } },
      recommendations: [rec(5, 1, "SIM-AMB-03"), rec(2, 2, "SIM-AMB-02", { is_spare: true }), rec(1, 3, "SIM-AMB-01")] }) });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    expect([box("SIM-AMB-03").checked, box("SIM-AMB-02").checked, box("SIM-AMB-01").checked]).toEqual([true, false, true]);
  });

  it("other reasons and lost GPS are shown in words", async () => {
    const b = backend({ vehicles: [vehicle(5, "SIM-AMB-03", { signal_lost: true }), vehicle(1, "SIM-AMB-01", { driver_on_duty: false, can_dispatch: false }),
      vehicle(2, "SIM-AMB-02", { status: "en_route", can_dispatch: false }), vehicle(4, "SIM-BKP-01", { driver_id: null, can_dispatch: false, vehicle_type: "backup" })] });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    const [r1, r2, r3] = screen.getAllByTestId("rec-row");
    expect(r1).toHaveTextContent("GPS signal lost");
    expect(r2).toHaveTextContent("driver off duty");
    expect(r3).toHaveTextContent("vehicle is en_route");
    expect(screen.getByTestId("other-row")).toHaveTextContent("no driver");
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("GPS signal lost for: SIM-AMB-03.");
  });

  it("with nothing ticked, Approve is disabled and says why", async () => {
    const b = backend();
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    await user.click(box("SIM-AMB-03"));
    expect(screen.getByRole("button", { name: "Approve dispatch" })).toBeDisabled();
    expect(screen.getByText("Choose at least one vehicle.")).toBeInTheDocument();
  });
});

describe("choosing differently from the AI", () => {
  it("a vehicle from 'Other vehicles' is marked as different and the optional reason is sent", async () => {
    const b = backend();
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    await user.click(box("SIM-AMB-03"));
    await user.click(screen.getByText("Other vehicles"));
    await user.click(box("SIM-BKP-01"));
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Different from the AI suggestion.");
    await user.type(within(dialog).getByLabelText("Reason (optional)"), "SIMULATED: road blocked, backup is closer");
    await user.click(within(dialog).getByRole("button", { name: "Confirm" }));
    await screen.findByText("✔ Dispatched: SIM-BKP-01.");
    expect(b.posts).toEqual([{ vehicle_ids: [4], override_reason: "SIMULATED: road blocked, backup is closer" }]);
  });
});

describe("refusals (TC-22)", () => {
  it("a vehicle taken in the meantime: warning, next best in one click, then Confirm", async () => {
    const b = backend();
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    Object.assign(b.fleet[0]!, { has_open_assignment: true, can_dispatch: false }); // another dispatcher was faster
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByTestId("dispatch-problem")).toHaveTextContent("Not sent: SIM-AMB-03 is already on another job.");
    await user.click(screen.getByRole("button", { name: "Use SIM-AMB-01 instead" }));
    expect(screen.getByTestId("summary-vehicles")).toHaveTextContent("SIM-AMB-01");
    expect(screen.getByTestId("summary-vehicles")).not.toHaveTextContent("SIM-AMB-03");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText("✔ Dispatched: SIM-AMB-01.")).toBeInTheDocument();
    expect(b.posts.map((p) => p.vehicle_ids)).toEqual([[5], [1]]);
  });

  it("an unavailable vehicle names the reason", async () => {
    const b = backend({ replies: [json(409, { code: "vehicle_unavailable", message: "x",
      details: { vehicles: [{ vehicle_id: 5, reason: "driver_off_duty" }], next_best: [] } })] });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    const p = await screen.findByTestId("dispatch-problem");
    expect(p).toHaveTextContent("Not sent: SIM-AMB-03: driver off duty.");
    expect(p).toHaveTextContent("No other recommended vehicle is free.");
  });

  it("a report that became fake cannot be confirmed", async () => {
    const b = backend({ replies: [json(409, { code: "incident_not_dispatchable", message: "x", details: { status: "fake" } })] });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByTestId("dispatch-problem")).toHaveTextContent("Not sent: this report is fake.");
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
  });
});

describe("special cases", () => {
  it("manual mode: no AI suggestion, the vehicle list is open and nothing is preticked", async () => {
    const b = backend({ incident: incident({ recommendations: [], allocation_summary: null, review_reasons: ["ai_failed"], severity: null }) });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    expect(await screen.findByTestId("manual-mode")).toHaveTextContent("Manual dispatch — no AI recommendation");
    await waitFor(() => expect(screen.getAllByTestId("other-row")).toHaveLength(4));
    expect(screen.getByRole("button", { name: "Approve dispatch" })).toBeDisabled();
    await user.click(box("SIM-AMB-01"));
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Manual dispatch (no AI recommendation).");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await screen.findByText("✔ Dispatched: SIM-AMB-01.");
  });

  it("a low-trust report can be sent, with the reminder that urgent reports are never held back", async () => {
    const b = backend({ incident: incident({ trust_tier: "low", trust_score: 30, status: "needs_check" }) });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    await user.click(screen.getByRole("button", { name: "Approve dispatch" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Low trust: the dispatcher decides; urgent reports are never held back.");
  });

  it("a fake report has no dispatch controls", async () => {
    const b = backend({ incident: incident({ status: "fake" }) });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    expect(await screen.findByText("This report is fake: no vehicle can be sent.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve dispatch" })).not.toBeInTheDocument();
  });

  it("an incident with vehicles already sent offers a backup and preticks nothing", async () => {
    const b = backend({ incident: incident({ status: "dispatched", assignments: [{ assignment_id: 7, vehicle_id: 5, approved_by: 9,
      hospital_id: null, status: "approved", approved_at: NOW }] }) });
    const user = await openIncident(b);
    await user.click(await screen.findByTestId("incident-card"));
    await ready();
    expect(screen.getByText(/You can send another vehicle \(backup\)/)).toBeInTheDocument();
    for (const plate of ["SIM-AMB-03", "SIM-AMB-01", "SIM-AMB-02", "SIM-BKP-01"]) expect(box(plate).checked).toBe(false);
    expect(screen.getByTestId("assignments")).toHaveTextContent("SIM-AMB-03 — approved");
    expect(screen.getByTestId("assignments")).toHaveTextContent("by user #9");
  });
});
