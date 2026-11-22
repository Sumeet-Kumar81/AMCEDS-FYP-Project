// Typed calls for the endpoints the backend has built so far. Types come from the generated
// contract (schema.ts), so a backend change that breaks a screen fails `npm run typecheck`.
// Endpoints that still answer 501 are added here in the group that builds their screen.
import { API_PREFIX, ApiClient } from "./client";
import type { components } from "./schema";

export type Schemas = components["schemas"];
export type ReportIn = Schemas["ReportIn"];
export type ReportAcceptedOut = Schemas["ReportAcceptedOut"];
export type LoginIn = Schemas["LoginIn"];
export type TokenOut = Schemas["TokenOut"];
export type MeOut = Schemas["MeOut"];
export type UserRole = Schemas["UserRole"];
export type Severity = Schemas["Severity"];
export type TrustTier = Schemas["TrustTier"];
export type IncidentStatus = Schemas["IncidentStatus"];
export type IncidentType = Schemas["IncidentType"];
export type IncidentSummaryOut = Schemas["IncidentSummaryOut"];
export type IncidentDetailOut = Schemas["IncidentDetailOut"];

/** `GET /health` (untyped in OpenAPI; shape fixed in backend/app/api/routes/health.py). */
export interface HealthOut {
  api: "ok" | string;
  database: "ok" | "down" | string;
}

/** Names of the services that are not "ok" in a health answer. */
export function downServices(health: HealthOut): string[] {
  return Object.entries(health)
    .filter(([, state]) => state !== "ok")
    .map(([name]) => name);
}

export function getHealth(client: ApiClient, signal?: AbortSignal): Promise<HealthOut> {
  return client.get<HealthOut>("/health", { auth: false, signal });
}

export interface SubmittedReport {
  report: ReportAcceptedOut;
  /** 200: a report with the same `client_request_id` was already saved; nothing new was stored (TC-04). */
  alreadySaved: boolean;
}

/** UC-01: resolves only after the server saved the report (201) or had already saved it (200). */
export async function submitReport(client: ApiClient, report: ReportIn): Promise<SubmittedReport> {
  const { status, data } = await client.requestWithStatus<ReportAcceptedOut>("POST", `${API_PREFIX}/reports`,
    { body: report, auth: false });
  return { report: data, alreadySaved: status === 200 };
}

/** Signs in and keeps the tokens in the client's memory store. */
export async function login(client: ApiClient, credentials: LoginIn): Promise<TokenOut> {
  const out = await client.post<TokenOut>(`${API_PREFIX}/auth/login`, credentials, { auth: false });
  client.tokens.set({ accessToken: out.access_token, refreshToken: out.refresh_token });
  return out;
}

export function getMe(client: ApiClient): Promise<MeOut> {
  return client.get<MeOut>(`${API_PREFIX}/auth/me`, { auth: true });
}

/** Ends the session on the server, then forgets the tokens even if the server call failed. */
export async function logout(client: ApiClient): Promise<void> {
  try {
    await client.post<void>(`${API_PREFIX}/auth/logout`, undefined, { auth: true });
  } finally {
    client.tokens.clear();
  }
}
