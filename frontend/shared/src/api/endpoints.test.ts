// Typed endpoint helpers: paths, what is public, token handling on login/logout.
import { describe, expect, it, vi } from "vitest";
import { ApiClient, apiBaseUrl } from "./client";
import { downServices, getHealth, getMe, login, logout, submitReport } from "./endpoints";

function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), { status });
}

function client(handler: (url: string, init: RequestInit) => Response) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetchFn = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    calls.push({ url: String(input), init });
    return handler(String(input), init);
  }) as typeof fetch;
  return { api: new ApiClient({ baseUrl: "http://api.test", fetch: fetchFn }), calls };
}

const header = (init: RequestInit) => (init.headers as Record<string, string>).Authorization;
const TOKENS = { access_token: "SIM-a", token_type: "bearer", expires_in: 900, refresh_token: "SIM-r" };

describe("endpoints", () => {
  it("login keeps the tokens in memory and /me uses them", async () => {
    const { api, calls } = client((url) => (url.endsWith("/login") ? json(200, TOKENS) : json(200, { username: "dispatcher1" })));
    await login(api, { username: "dispatcher1", password: "SIMULATED-pass" });
    expect(api.tokens.get()).toEqual({ accessToken: "SIM-a", refreshToken: "SIM-r" });
    await getMe(api);
    expect(calls[1]!.url).toBe("http://api.test/api/v1/auth/me");
    expect(header(calls[1]!.init)).toBe("Bearer SIM-a");
  });

  it("a report is always sent without a token, even when signed in", async () => {
    const { api, calls } = client(() => json(201, { reference_no: "INC-000001", status: "new", received_at: "2026-11-22T08:00:00Z" }));
    api.tokens.set({ accessToken: "SIM-a", refreshToken: "SIM-r" });
    const out = await submitReport(api, { description: "SIMULATED: fire", channel: "web", client_request_id: "sim-1" });
    expect(out).toEqual({ report: expect.objectContaining({ reference_no: "INC-000001" }), alreadySaved: false });
    expect(calls[0]!.url).toBe("http://api.test/api/v1/reports");
    expect(header(calls[0]!.init)).toBeUndefined();
  });

  it("a resend answered 200 is reported as already saved (TC-04)", async () => {
    const { api } = client(() => json(200, { reference_no: "INC-000001", status: "new", received_at: "2026-11-22T08:00:00Z" }));
    const out = await submitReport(api, { description: "SIMULATED: fire", channel: "web", client_request_id: "sim-1" });
    expect(out.alreadySaved).toBe(true);
  });

  it("logout forgets the tokens even when the server call fails", async () => {
    const { api } = client(() => json(500, { code: "internal", message: "SIMULATED" }));
    api.tokens.set({ accessToken: "SIM-a", refreshToken: "SIM-r" });
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    await expect(logout(api)).rejects.toBeTruthy();
    expect(api.tokens.get()).toBeNull();
  });

  it("health is public and lists the services that are down", async () => {
    const { api, calls } = client(() => json(200, { api: "ok", database: "down" }));
    const health = await getHealth(api);
    expect(calls[0]!.url).toBe("http://api.test/health");
    expect(downServices(health)).toEqual(["database"]);
    expect(downServices({ api: "ok", database: "ok" })).toEqual([]);
  });

  it("the API address comes from VITE_API_URL", () => {
    expect(apiBaseUrl({})).toBe("http://localhost:8000");
    expect(apiBaseUrl({ VITE_API_URL: "http://10.0.0.5:8000/" })).toBe("http://10.0.0.5:8000");
  });
});
