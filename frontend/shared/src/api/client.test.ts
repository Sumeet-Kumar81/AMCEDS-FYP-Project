// ApiClient (B1-A3-01): auth header, refresh on 401 (once, shared), session end, error mapping,
// 503 banner hook, timeouts. Fake fetch only; no network.
import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "./client";
import { ApiError } from "./errors";
import { TokenStore } from "./tokens";

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function setup(handler: Handler, opts: { loggedIn?: boolean; timeoutMs?: number } = {}) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetchFn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    calls.push({ url, init });
    return handler(url, init);
  }) as unknown as typeof fetch;
  const tokens = new TokenStore();
  if (opts.loggedIn !== false) tokens.set({ accessToken: "SIM-access-1", refreshToken: "SIM-refresh-1" });
  const onSessionEnded = vi.fn();
  const onServiceUnavailable = vi.fn();
  const client = new ApiClient({ baseUrl: "http://api.test/", tokens, fetch: fetchFn, onSessionEnded,
    onServiceUnavailable, timeoutMs: opts.timeoutMs });
  const auth = (i: number) => (calls[i]!.init.headers as Record<string, string>).Authorization;
  return { client, calls, tokens, onSessionEnded, onServiceUnavailable, auth };
}

const REFRESHED = { access_token: "SIM-access-2", token_type: "bearer", expires_in: 900, refresh_token: "SIM-refresh-2" };
const EXPIRED = { code: "session_ended", message: "Your session has ended. Please sign in again.", details: null };

describe("requests", () => {
  it("joins the base URL, sends JSON and the access token", async () => {
    const { client, calls, auth } = setup(() => json(200, { ok: true }));
    await expect(client.post("/api/v1/x", { a: 1 })).resolves.toEqual({ ok: true });
    expect(calls[0]!.url).toBe("http://api.test/api/v1/x");
    expect(calls[0]!.init.method).toBe("POST");
    expect(calls[0]!.init.body).toBe('{"a":1}');
    expect(auth(0)).toBe("Bearer SIM-access-1");
  });

  it("never sends the token on a public call", async () => {
    const { client, auth } = setup(() => json(201, {}));
    await client.post("/api/v1/reports", {}, { auth: false });
    expect(auth(0)).toBeUndefined();
  });

  it("returns undefined for 204 No Content", async () => {
    const { client } = setup(() => new Response(null, { status: 204 }));
    await expect(client.post("/api/v1/auth/logout")).resolves.toBeUndefined();
  });
});

describe("refresh on 401", () => {
  it("refreshes once and retries with the new token", async () => {
    let n = 0;
    const { client, calls, tokens, auth } = setup((url) => {
      if (url.endsWith("/auth/refresh")) return json(200, REFRESHED);
      return ++n === 1 ? json(401, EXPIRED) : json(200, { me: true });
    });
    await expect(client.get("/api/v1/auth/me")).resolves.toEqual({ me: true });
    expect(calls.map((c) => c.url.replace("http://api.test", ""))).toEqual([
      "/api/v1/auth/me", "/api/v1/auth/refresh", "/api/v1/auth/me"]);
    expect(JSON.parse(String(calls[1]!.init.body))).toEqual({ refresh_token: "SIM-refresh-1" });
    expect(auth(1)).toBeUndefined(); // the refresh call itself carries no access token
    expect(auth(2)).toBe("Bearer SIM-access-2");
    expect(tokens.get()).toEqual({ accessToken: "SIM-access-2", refreshToken: "SIM-refresh-2" });
  });

  it("parallel 401s share one refresh", async () => {
    const seen = new Set<string>();
    const { client, calls } = setup((url, init) => {
      if (url.endsWith("/auth/refresh")) return json(200, REFRESHED);
      const token = (init.headers as Record<string, string>).Authorization!;
      seen.add(token);
      return token.endsWith("-1") ? json(401, EXPIRED) : json(200, {});
    });
    await Promise.all([client.get("/a"), client.get("/b"), client.get("/c")]);
    expect(calls.filter((c) => c.url.endsWith("/auth/refresh"))).toHaveLength(1);
    expect(seen).toEqual(new Set(["Bearer SIM-access-1", "Bearer SIM-access-2"]));
  });

  it("ends the session when the refresh fails", async () => {
    const { client, tokens, onSessionEnded } = setup((url) =>
      url.endsWith("/auth/refresh") ? json(401, EXPIRED) : json(401, EXPIRED));
    const error = await client.get("/api/v1/auth/me").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("session_ended");
    expect(tokens.get()).toBeNull();
    expect(onSessionEnded).toHaveBeenCalledTimes(1);
  });

  it("ends the session when the retry is still 401", async () => {
    const { client, tokens, onSessionEnded } = setup((url) =>
      url.endsWith("/auth/refresh") ? json(200, REFRESHED) : json(401, EXPIRED));
    await expect(client.get("/x")).rejects.toMatchObject({ status: 401 });
    expect(tokens.get()).toBeNull();
    expect(onSessionEnded).toHaveBeenCalledTimes(1);
  });

  it("does not refresh a public call or when signed out", async () => {
    const wrong = { code: "invalid_credentials", message: "Invalid username or password.", details: null };
    const { client, calls, onSessionEnded } = setup(() => json(401, wrong), { loggedIn: false });
    await expect(client.post("/api/v1/auth/login", {}, { auth: false })).rejects.toMatchObject({
      code: "invalid_credentials" });
    expect(calls).toHaveLength(1);
    expect(onSessionEnded).not.toHaveBeenCalled();
  });

  it("a 403 is not a session problem", async () => {
    const { client, calls, tokens } = setup(() => json(403, { code: "forbidden", message: "Your role may not do this." }));
    await expect(client.get("/api/v1/admin/users")).rejects.toMatchObject({ status: 403, code: "forbidden" });
    expect(calls).toHaveLength(1);
    expect(tokens.get()).not.toBeNull();
  });
});

describe("error mapping", () => {
  it("keeps the contract body of a 422, including the field problems", async () => {
    const body = { code: "validation_error", message: "The request is not valid.",
      details: [{ loc: ["body", "description"], msg: "String should have at least 1 character", type: "string_too_short" }] };
    const { client } = setup(() => json(422, body));
    const error = (await client.post("/r", {}).catch((e: unknown) => e)) as ApiError;
    expect([error.status, error.code, error.message]).toEqual([422, "validation_error", "The request is not valid."]);
    expect(error.validationIssues[0]!.loc).toEqual(["body", "description"]);
  });

  it("501 is reported as not built, with its task", async () => {
    const { client } = setup(() => json(501, { code: "not_implemented", message: "not yet", details: { task: "B1-A1-20" } }));
    const error = (await client.get("/api/v1/incidents").catch((e: unknown) => e)) as ApiError;
    expect(error.notImplemented).toBe(true);
    expect(error.details).toEqual({ task: "B1-A1-20" });
  });

  it("503 calls the service banner hook and is still an error", async () => {
    const body = { code: "service_unavailable", message: "Not saved.", details: null };
    const { client, onServiceUnavailable } = setup(() => json(503, body));
    await expect(client.post("/api/v1/reports", {}, { auth: false })).rejects.toMatchObject({ serviceUnavailable: true });
    expect(onServiceUnavailable).toHaveBeenCalledTimes(1);
  });

  it("an error without the contract body becomes bad_response", async () => {
    const { client } = setup(() => new Response("<html>502 Bad Gateway</html>", { status: 502 }));
    await expect(client.get("/x")).rejects.toMatchObject({ status: 502, code: "bad_response" });
  });

  it("no answer becomes network_error with status 0", async () => {
    const { client } = setup(() => Promise.reject(new TypeError("Failed to fetch")));
    await expect(client.get("/x")).rejects.toMatchObject({ status: 0, code: "network_error", noConnection: true });
  });

  it("a slow server becomes timeout", async () => {
    const { client } = setup((_url, init) => new Promise<Response>((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    }), { timeoutMs: 20 });
    await expect(client.get("/x")).rejects.toMatchObject({ status: 0, code: "timeout" });
  });

  it("a call cancelled by the screen is not turned into an API error", async () => {
    const { client } = setup((_url, init) => new Promise<Response>((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    }));
    const controller = new AbortController();
    const pending = client.get("/x", { signal: controller.signal });
    controller.abort();
    const error = await pending.catch((e: unknown) => e);
    expect(error).not.toBeInstanceOf(ApiError);
  });
});
