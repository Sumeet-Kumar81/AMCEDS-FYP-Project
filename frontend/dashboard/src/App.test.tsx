// Dashboard sign-in and role routing (B1-A3-04): role homes, wrong password, lockout (TC-32), drivers
// refused, guards, session end, sign-out, idle sign-out (NFR-C4). A fake backend with the real rules.
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { ApiClient } from "@amceds/shared";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Root } from "./App";

const USERS: Record<string, { password: string; role: string; full_name: string; user_id: number }> = {
  dispatcher1: { password: "SIM-pass-1", role: "dispatcher", full_name: "SIMULATED Dispatcher One", user_id: 2 },
  admin1: { password: "SIM-pass-2", role: "admin", full_name: "SIMULATED Admin", user_id: 1 },
  driver01: { password: "SIM-pass-3", role: "driver", full_name: "SIMULATED Driver", user_id: 4 },
};

function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), { status });
}

/** In-memory backend: lockout after 5 wrong passwords, sessions that can be ended, call log. */
function fakeBackend(opts: { down?: boolean } = {}) {
  const calls: { method: string; path: string; body?: unknown; auth?: string }[] = [];
  const failures: Record<string, number> = {};
  let sessions = 0;
  const live = new Map<string, string>(); // access token -> username
  const ended = new Set<string>();
  const fetchFn = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const path = String(input).replace("http://api.test", "");
    const auth = (init.headers as Record<string, string> | undefined)?.Authorization;
    const body = init.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method: init.method ?? "GET", path, body, auth });
    if (opts.down) throw new TypeError("Failed to fetch");
    if (path === "/health") return json(200, { api: "ok", database: "ok" });
    if (path === "/api/v1/auth/login") {
      const u = USERS[body.username];
      if ((failures[body.username] ?? 0) >= 5) {
        return json(401, { code: "account_locked", message: "Too many wrong passwords. The account is locked; try again in 15 minute(s).", details: null });
      }
      if (!u || u.password !== body.password) {
        failures[body.username] = (failures[body.username] ?? 0) + 1;
        return json(401, { code: "invalid_credentials", message: "Invalid username or password.", details: null });
      }
      const token = `SIM-access-${++sessions}`;
      live.set(token, body.username);
      return json(200, { access_token: token, token_type: "bearer", expires_in: 900, refresh_token: `SIM-refresh-${sessions}` });
    }
    const token = auth?.replace("Bearer ", "") ?? "";
    const who = live.get(token);
    const endedBody = { code: "session_ended", message: "Your session has ended. Please sign in again.", details: null };
    if (path === "/api/v1/auth/refresh") return json(401, endedBody);
    if (!who || ended.has(token)) return json(401, endedBody);
    if (path === "/api/v1/auth/logout") {
      ended.add(token);
      return json(204);
    }
    if (path === "/api/v1/auth/me") {
      const u = USERS[who]!;
      return json(200, { user_id: u.user_id, full_name: u.full_name, username: who, role: u.role, phone: null, on_duty: false });
    }
    return json(404, { code: "not_found", message: "no such path", details: null });
  }) as typeof fetch;
  const client = new ApiClient({ baseUrl: "http://api.test", fetch: fetchFn });
  return { client, calls, endAllSessions: () => live.forEach((_u, t) => ended.add(t)) };
}

function Where() {
  return <p data-testid="path">{useLocation().pathname}</p>;
}

function renderAt(path: string, backend = fakeBackend()) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Root client={backend.client} />
      <Where />
    </MemoryRouter>,
  );
  return backend;
}

async function signIn(user: ReturnType<typeof userEvent.setup>, username: string, password: string) {
  await user.clear(screen.getByLabelText("Username"));
  await user.type(screen.getByLabelText("Username"), username);
  await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

const path = () => screen.getByTestId("path").textContent;
const meCalls = (b: ReturnType<typeof fakeBackend>) => b.calls.filter((c) => c.path === "/api/v1/auth/me").length;

afterEach(() => vi.useRealTimers());

describe("signing in", () => {
  it("a dispatcher lands on the incident queue with name and role shown", async () => {
    const user = userEvent.setup();
    renderAt("/");
    expect(path()).toBe("/login");
    await signIn(user, "dispatcher1", "SIM-pass-1");
    expect(await screen.findByRole("heading", { name: "Incident queue" })).toBeInTheDocument();
    expect(path()).toBe("/queue");
    expect(screen.getByText("Signed in as SIMULATED Dispatcher One (Dispatcher)")).toBeInTheDocument();
    expect(screen.getByText(/comes in the next step \(F4, task B1-A1-20\)/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Administration" })).not.toBeInTheDocument();
  });

  it("an admin lands on administration", async () => {
    const user = userEvent.setup();
    renderAt("/login");
    await signIn(user, "admin1", "SIM-pass-2");
    expect(await screen.findByRole("heading", { name: "Administration" })).toBeInTheDocument();
    expect(path()).toBe("/admin");
    expect(screen.getByText(/not built yet \(task B1-A1-31\)/)).toBeInTheDocument();
  });

  it("a driver is refused and the session is ended on the server", async () => {
    const user = userEvent.setup();
    const backend = renderAt("/login");
    await signIn(user, "driver01", "SIM-pass-3");
    expect(await screen.findByRole("alert")).toHaveTextContent("Drivers use the mobile app");
    expect(path()).toBe("/login");
    const logout = backend.calls.find((c) => c.path === "/api/v1/auth/logout");
    expect(logout?.auth).toBe("Bearer SIM-access-1");
  });

  it("a wrong password says so and empties the password box", async () => {
    const user = userEvent.setup();
    renderAt("/login");
    await signIn(user, "dispatcher1", "wrong-SIM");
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong username or password.");
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(path()).toBe("/login");
  });

  it("after 5 wrong passwords the account is locked, even for the right one (TC-32)", async () => {
    const user = userEvent.setup();
    renderAt("/login");
    for (let i = 0; i < 5; i++) await signIn(user, "dispatcher1", `wrong-${i}`);
    await signIn(user, "dispatcher1", "SIM-pass-1");
    expect(await screen.findByRole("alert")).toHaveTextContent("The account is locked; try again in 15 minute(s).");
    expect(path()).toBe("/login");
  });

  it("empty fields are not sent", async () => {
    const user = userEvent.setup();
    const backend = renderAt("/login");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter your username and password.");
    expect(backend.calls.filter((c) => c.path.includes("/auth/"))).toHaveLength(0);
  });

  it("no server: a clear message", async () => {
    const user = userEvent.setup();
    renderAt("/login", fakeBackend({ down: true }));
    await signIn(user, "dispatcher1", "SIM-pass-1");
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server.");
  });

  it("the password is never put in the URL or browser storage", async () => {
    const user = userEvent.setup();
    localStorage.clear();
    sessionStorage.clear();
    renderAt("/login");
    await signIn(user, "dispatcher1", "SIM-pass-1");
    await screen.findByRole("heading", { name: "Incident queue" });
    expect(path()).not.toContain("SIM-pass");
    expect(window.location.href).not.toContain("SIM-pass");
    expect(localStorage.length + sessionStorage.length).toBe(0); // tokens stay in memory
  });
});

describe("guards", () => {
  it("a signed-out visitor is sent to login and brought back afterwards", async () => {
    const user = userEvent.setup();
    renderAt("/queue");
    expect(path()).toBe("/login");
    await signIn(user, "dispatcher1", "SIM-pass-1");
    await waitFor(() => expect(path()).toBe("/queue"));
  });

  it("a dispatcher cannot open administration", async () => {
    const user = userEvent.setup();
    renderAt("/admin");
    await signIn(user, "dispatcher1", "SIM-pass-1");
    expect(await screen.findByRole("heading", { name: "Not allowed" })).toBeInTheDocument();
    expect(screen.queryByText(/B1-A1-31/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Go to my start page" }));
    expect(path()).toBe("/queue");
  });

  it("an admin cannot open the incident queue", async () => {
    const user = userEvent.setup();
    renderAt("/queue");
    await signIn(user, "admin1", "SIM-pass-2");
    expect(await screen.findByRole("heading", { name: "Not allowed" })).toBeInTheDocument();
  });

  it("unknown paths go to the start page of the role", async () => {
    const user = userEvent.setup();
    renderAt("/no-such-page");
    expect(path()).toBe("/login");
    await signIn(user, "dispatcher1", "SIM-pass-1");
    await waitFor(() => expect(path()).toBe("/queue"));
  });
});

describe("signing out", () => {
  it("sign out ends the server session and says so", async () => {
    const user = userEvent.setup();
    const backend = renderAt("/login");
    await signIn(user, "dispatcher1", "SIM-pass-1");
    await user.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByText("You have signed out.")).toBeInTheDocument();
    expect(path()).toBe("/login");
    expect(backend.calls.some((c) => c.path === "/api/v1/auth/logout")).toBe(true);
  });

  it("a session ended by the server sends the user to login with a message", async () => {
    const user = userEvent.setup();
    const backend = renderAt("/login");
    await signIn(user, "dispatcher1", "SIM-pass-1");
    await screen.findByRole("heading", { name: "Incident queue" });
    backend.endAllSessions();
    await act(async () => {
      await backend.client.get("/api/v1/auth/me").catch(() => undefined); // any later call finds it ended
    });
    expect(await screen.findByText("Your session has ended. Please sign in again.")).toBeInTheDocument();
    expect(path()).toBe("/login");
  });
});

describe("idle sign-out (NFR-C4)", () => {
  async function signedInWithFakeClock() {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const backend = renderAt("/login");
    await signIn(user, "dispatcher1", "SIM-pass-1");
    await screen.findByRole("heading", { name: "Incident queue" });
    await act(async () => {}); // let the layout's effects (the idle timer) start before the clock moves
    return { user, backend };
  }
  const minutes = (m: number) => act(async () => { vi.advanceTimersByTime(m * 60_000); });

  it("warns after 28 minutes and signs out after 30", async () => {
    const { backend } = await signedInWithFakeClock();
    await minutes(27.9);
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await minutes(0.2);
    expect(screen.getByRole("alertdialog")).toHaveTextContent("you will be signed out in 2 minutes");
    await minutes(2);
    expect(await screen.findByText("You were signed out after 30 minutes without activity.")).toBeInTheDocument();
    expect(path()).toBe("/login");
    expect(backend.calls.some((c) => c.path === "/api/v1/auth/logout")).toBe(true);
  });

  it("any key press or click starts the 30 minutes again", async () => {
    await signedInWithFakeClock();
    await minutes(20);
    await act(async () => { window.dispatchEvent(new KeyboardEvent("keydown", { key: "a" })); });
    await minutes(20);
    expect(screen.getByRole("heading", { name: "Incident queue" })).toBeInTheDocument();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await minutes(10.5);
    expect(await screen.findByText(/signed out after 30 minutes/)).toBeInTheDocument();
  });

  it("'Stay signed in' (or any touch) removes the warning and keeps the session", async () => {
    const { user } = await signedInWithFakeClock();
    await minutes(28.5);
    await user.click(screen.getByRole("button", { name: "Stay signed in" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await minutes(25);
    expect(screen.getByRole("heading", { name: "Incident queue" })).toBeInTheDocument();
  });

  it("the 'Stay signed in' button itself tells the server (keyboard use)", async () => {
    const { backend } = await signedInWithFakeClock();
    await minutes(28.5);
    const before = meCalls(backend);
    await act(async () => { screen.getByRole("button", { name: "Stay signed in" }).click(); }); // Enter key: no pointer event
    await waitFor(() => expect(meCalls(backend)).toBe(before + 1));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("while the user is active the server is told every 5 minutes, otherwise not", async () => {
    const { backend } = await signedInWithFakeClock();
    const start = meCalls(backend);
    await minutes(5.1);
    expect(meCalls(backend)).toBe(start); // no activity: no call
    for (let i = 0; i < 3; i++) {
      await act(async () => { window.dispatchEvent(new KeyboardEvent("keydown", { key: "a" })); });
      await minutes(5);
    }
    await waitFor(() => expect(meCalls(backend)).toBe(start + 3));
  });

  it("background calls do not count as activity", async () => {
    const { backend } = await signedInWithFakeClock();
    for (let i = 0; i < 6; i++) {
      await minutes(5);
      await act(async () => { await backend.client.get("/api/v1/auth/me").catch(() => undefined); }); // like the F4 refresh
    }
    expect(await screen.findByText(/signed out after 30 minutes/)).toBeInTheDocument();
  });
});
