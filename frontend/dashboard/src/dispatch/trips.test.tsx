// Trip tracking on the review screen (F6, uses B1-A1-26): state of each dispatched vehicle from its
// timestamps, the on-screen "no answer" reminder, cancel with confirmation, hospital change, history
// only for finished trips, and driver progress appearing after the 5-s refresh. Fake backend; SIMULATED.
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient } from "@tanstack/react-query";
import { ApiClient, type AssignmentOut, type IncidentDetailOut } from "@amceds/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Root } from "../App";

const ago = (s: number) => new Date(Date.now() - s * 1000).toISOString();
const HOSPITALS = [{ hospital_id: 1, name: "SIMULATED General Hospital A", lat: 27.7, lon: 68.86 },
  { hospital_id: 2, name: "SIMULATED General Hospital B", lat: 27.71, lon: 68.87 }];
const FLEET = [5, 1, 4].map((id, k) => ({ vehicle_id: id, plate_number: ["SIM-AMB-03", "SIM-AMB-01", "SIM-BKP-01"][k], vehicle_type: k === 2 ? "backup" : "ambulance",
  status: "assigned", station_name: null, patient_capacity: 2, driver_id: 100 + id, driver_name: `SIMULATED Driver ${id}`, driver_on_duty: true,
  lat: 27.7, lon: 68.85, last_seen_at: ago(1), signal_lost: false, has_open_assignment: true, can_dispatch: false, distance_meters: 900,
  distance_is_approximate: true }));

function asg(id: number, vehicle: number, extra: Partial<AssignmentOut> = {}): AssignmentOut {
  return { assignment_id: id, vehicle_id: vehicle, approved_by: 2, hospital_id: null, status: "approved", approved_at: ago(10), ...extra };
}

function incident(assignments: AssignmentOut[], extra: Partial<IncidentDetailOut> = {}): IncidentDetailOut {
  return { incident_id: 1, reference_no: "INC-000001", channel: "web", received_at: ago(600), language: "Roman Urdu",
    location: { lat: 27.71, lon: 68.85, text: null, source: "gps" }, incident_type: "accident", severity: "critical", victims_estimate: 2,
    confidence: 0.9, trust_score: 60, trust_tier: "medium", group_id: null, status: "dispatched", review_reasons: [],
    original_text: "SIMULATED: takkar", audio_ref: null, reporter_name: null, ai_details: null, trust_signals: [],
    allocation_summary: { needed: { ambulance: 1 } }, duplicate_candidates: [], recommendations: [], assignments,
    dispatcher_decision: null, ...extra };
}

function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), { status });
}

function backend(start: IncidentDetailOut, replies: Response[] = []) {
  const state = { inc: start };
  const calls: { method: string; path: string; body?: unknown }[] = [];
  const fetchFn = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const path = String(input).replace("http://api.test", "");
    const method = init.method ?? "GET";
    const body = init.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body });
    if (path === "/health") return json(200, { api: "ok", database: "ok" });
    if (path === "/api/v1/auth/login") return json(200, { access_token: "SIM-a", token_type: "bearer", expires_in: 900, refresh_token: "SIM-r" });
    if (path === "/api/v1/auth/me") return json(200, { user_id: 2, full_name: "SIMULATED Dispatcher", username: "dispatcher1", role: "dispatcher", phone: null, on_duty: false });
    if (path === "/api/v1/incidents/1") return json(200, state.inc);
    if (path.startsWith("/api/v1/vehicles")) return json(200, FLEET);
    if (path === "/api/v1/hospitals") return json(200, HOSPITALS);
    const m = path.match(/^\/api\/v1\/assignments\/(\d+)\/(cancel|hospital)$/);
    if (m) {
      const scripted = replies.shift();
      if (scripted) return scripted;
      const id = Number(m[1]);
      const list = state.inc.assignments!.map((a) => a.assignment_id !== id ? a
        : m[2] === "cancel" ? { ...a, status: "cancelled" as const } : { ...a, hospital_id: body.hospital_id });
      state.inc = { ...state.inc, assignments: list };
      return json(200, list.find((a) => a.assignment_id === id));
    }
    return json(404, { code: "not_found", message: "no such path", details: null });
  }) as typeof fetch;
  return { client: new ApiClient({ baseUrl: "http://api.test", fetch: fetchFn }), calls, state };
}

async function open(b: ReturnType<typeof backend>, user = userEvent.setup()) {
  render(<MemoryRouter initialEntries={["/incidents/1"]}><Root client={b.client} queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })} /></MemoryRouter>);
  await user.type(screen.getByLabelText("Username"), "dispatcher1");
  await user.type(screen.getByLabelText("Password"), "SIM-pass");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findAllByTestId("trip");
  await waitFor(() => expect(screen.getAllByTestId("trip")[0]).toHaveTextContent("SIM-")); // plates come with the vehicle list
  return user;
}

const trip = (n = 0) => screen.getAllByTestId("trip")[n]!;

afterEach(() => vi.useRealTimers());

describe("where each trip stands", () => {
  it.each<[Partial<AssignmentOut>, string]>([
    [{ status: "approved" }, "Waiting for the driver to accept"],
    [{ status: "accepted", accepted_at: ago(8) }, "On the way"],
    [{ status: "accepted", accepted_at: ago(8), on_scene_at: ago(6) }, "On scene"],
    [{ status: "accepted", accepted_at: ago(8), on_scene_at: ago(6), picked_up_at: ago(4) }, "Patient picked up"],
    [{ status: "accepted", accepted_at: ago(8), on_scene_at: ago(6), picked_up_at: ago(4), at_hospital_at: ago(2) }, "At hospital"],
    [{ status: "completed", accepted_at: ago(8), completed_at: ago(1) }, "Trip completed — vehicle free"],
    [{ status: "declined", declined_at: ago(5), decline_reason: "vehicle_problem" }, "Declined: vehicle problem"],
    [{ status: "cancelled" }, "Cancelled"],
  ])("%j → %s", async (extra, label) => {
    await open(backend(incident([asg(7, 5, extra)])));
    expect(within(trip()).getByTestId("trip-state")).toHaveTextContent(label);
    expect(trip()).toHaveTextContent("SIM-AMB-03");
  });

  it("shows a timeline with each step's time, the approver and the hospital", async () => {
    await open(backend(incident([asg(7, 5, { status: "accepted", accepted_at: ago(8), on_scene_at: ago(6), hospital_id: 1 })])));
    const steps = within(trip()).getByRole("list", { name: "timeline" });
    expect([...steps.querySelectorAll("li")].map((li) => li.textContent?.split(" ")[0])).toEqual(["Approved", "Accepted", "On"]);
    expect(trip()).toHaveTextContent("by you");
    await waitFor(() => expect(trip()).toHaveTextContent("Hospital: SIMULATED General Hospital A"));
  });
});

describe("no answer from the driver (on-screen reminder only)", () => {
  it("appears for an approved assignment older than 60 s, not before and not once accepted", async () => {
    await open(backend(incident([asg(7, 5, { approved_at: ago(190) }), asg(8, 1, { approved_at: ago(20) }),
      asg(9, 4, { status: "accepted", approved_at: ago(400), accepted_at: ago(390) })])));
    expect(within(trip(0)).getByTestId("no-answer")).toHaveTextContent("No answer from the driver for 3 min");
    expect(within(trip(1)).queryByTestId("no-answer")).not.toBeInTheDocument();
    expect(within(trip(2)).queryByTestId("no-answer")).not.toBeInTheDocument();
  });

  it("appears by itself when the minute passes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open(backend(incident([asg(7, 5, { approved_at: ago(50) })])), userEvent.setup({ advanceTimers: vi.advanceTimersByTime }));
    expect(screen.queryByTestId("no-answer")).not.toBeInTheDocument();
    await act(async () => { vi.advanceTimersByTime(16_000); });
    expect(await screen.findByTestId("no-answer")).toHaveTextContent("for 1 min");
  });
});

describe("cancel", () => {
  it("needs a confirmation; Keep and Escape send nothing; Confirm sends the reason and says to inform the driver", async () => {
    const b = backend(incident([asg(7, 5)]));
    const user = await open(b);
    await user.click(within(trip()).getByRole("button", { name: "Cancel vehicle" }));
    expect(screen.getByRole("dialog", { name: "Cancel SIM-AMB-03?" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Keep it" }));
    await user.click(within(trip()).getByRole("button", { name: "Cancel vehicle" }));
    await user.type(screen.getByLabelText("Reason (optional)"), "x{Escape}");
    expect(screen.queryByRole("dialog", { name: "Cancel SIM-AMB-03?" })).not.toBeInTheDocument();
    expect(b.calls.filter((c) => c.path.endsWith("/cancel"))).toHaveLength(0);

    await user.click(within(trip()).getByRole("button", { name: "Cancel vehicle" }));
    await user.type(screen.getByLabelText("Reason (optional)"), "SIMULATED: wrong vehicle");
    await user.click(screen.getByRole("button", { name: "Cancel this vehicle" }));
    expect(await screen.findByText("✔ SIM-AMB-03 cancelled — inform the driver.")).toBeInTheDocument();
    expect(b.calls.find((c) => c.path.endsWith("/cancel"))).toMatchObject({ method: "POST", path: "/api/v1/assignments/7/cancel",
      body: { reason: "SIMULATED: wrong vehicle" } });
    await waitFor(() => expect(within(trip()).getByTestId("trip-state")).toHaveTextContent("Cancelled"));
    expect(within(trip()).queryByRole("button", { name: "Cancel vehicle" })).not.toBeInTheDocument();
  });

  it("a refusal is shown and never as success", async () => {
    const b = backend(incident([asg(7, 5)]), [json(409, { code: "invalid_transition", message: "The assignment is 'completed'.", details: null })]);
    const user = await open(b);
    await user.click(within(trip()).getByRole("button", { name: "Cancel vehicle" }));
    await user.click(screen.getByRole("button", { name: "Cancel this vehicle" }));
    expect(await within(trip()).findByText("Not done: The assignment is 'completed'.")).toBeInTheDocument();
    expect(screen.queryByText(/cancelled — inform the driver/)).not.toBeInTheDocument();
  });
});

describe("hospital change", () => {
  it("picks another hospital, saves it and says to inform the driver", async () => {
    const b = backend(incident([asg(7, 5, { status: "accepted", accepted_at: ago(5), hospital_id: 1 })]));
    const user = await open(b);
    await user.click(within(trip()).getByRole("button", { name: "Change hospital" }));
    const save = within(trip()).getByRole("button", { name: "Save" });
    await waitFor(() => expect(within(trip()).getByRole("option", { name: "SIMULATED General Hospital B" })).toBeInTheDocument());
    expect(save).toBeDisabled(); // same hospital as now
    await user.selectOptions(within(trip()).getByRole("combobox"), "2");
    await user.click(save);
    expect(await screen.findByText("✔ Hospital changed to SIMULATED General Hospital B — inform the driver.")).toBeInTheDocument();
    expect(b.calls.find((c) => c.path.endsWith("/hospital"))).toMatchObject({ method: "PATCH", body: { hospital_id: 2 } });
    await waitFor(() => expect(trip()).toHaveTextContent("Hospital: SIMULATED General Hospital B"));
  });
});

describe("history and refresh", () => {
  it("finished trips have no buttons; a closed incident shows the history and no dispatch controls", async () => {
    await open(backend(incident([asg(7, 5, { status: "completed", accepted_at: ago(8), completed_at: ago(1) }),
      asg(8, 1, { status: "declined", declined_at: ago(5), decline_reason: "too_far" })], { status: "closed" })));
    expect(screen.getAllByTestId("trip")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Cancel vehicle" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Change hospital" })).not.toBeInTheDocument();
    expect(screen.getByText("This report is closed: no vehicle can be sent.")).toBeInTheDocument();
    expect(within(trip(1)).getByTestId("trip-state")).toHaveTextContent("Declined: too far");
  });

  it("what the driver reports appears after the 5-s refresh", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const b = backend(incident([asg(7, 5)]));
    await open(b, userEvent.setup({ advanceTimers: vi.advanceTimersByTime }));
    expect(within(trip()).getByTestId("trip-state")).toHaveTextContent("Waiting for the driver to accept");
    b.state.inc = incident([asg(7, 5, { status: "accepted", accepted_at: ago(2), on_scene_at: ago(1) })], { status: "on_scene" });
    await act(async () => { vi.advanceTimersByTime(5_500); });
    await waitFor(() => expect(within(trip()).getByTestId("trip-state")).toHaveTextContent("On scene"));
  });
});
