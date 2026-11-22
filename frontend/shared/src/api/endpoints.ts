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

// ---------------------------------------------------------------- incidents (B1-A1-20, read-only, dispatcher)
export type RecommendationOut = Schemas["RecommendationOut"];
export type TrustSignalOut = Schemas["TrustSignalOut"];
export type LocationOut = Schemas["LocationOut"];

export interface IncidentQuery {
  status?: IncidentStatus[];
  severity?: (Severity | "unknown")[];
  includeClosed?: boolean;
  limit?: number;
  offset?: number;
}

/** Queue order comes from the server: critical, high, unknown, medium, low, then longest-waiting. */
export function listIncidents(client: ApiClient, query: IncidentQuery = {}, signal?: AbortSignal): Promise<IncidentSummaryOut[]> {
  const params = new URLSearchParams();
  for (const s of query.status ?? []) params.append("status", s);
  for (const s of query.severity ?? []) params.append("severity", s);
  if (query.includeClosed) params.set("include_closed", "true");
  if (query.limit != null) params.set("limit", String(query.limit));
  if (query.offset != null) params.set("offset", String(query.offset));
  const qs = params.toString();
  return client.get<IncidentSummaryOut[]>(`${API_PREFIX}/incidents${qs ? `?${qs}` : ""}`, { auth: true, signal });
}

export function getIncident(client: ApiClient, incidentId: number, signal?: AbortSignal): Promise<IncidentDetailOut> {
  return client.get<IncidentDetailOut>(`${API_PREFIX}/incidents/${encodeURIComponent(String(incidentId))}`, { auth: true, signal });
}

// ---------------------------------------------------------------- dispatch (B1-A1-25, dispatcher)
export type VehicleOut = Schemas["VehicleOut"];
export type DispatchIn = Schemas["DispatchIn"];
export type AssignmentOut = Schemas["AssignmentOut"];
export type VehicleType = Schemas["VehicleType"];

export interface VehicleQuery {
  incidentId?: number;
  type?: VehicleType[];
  availableOnly?: boolean;
}

/** All vehicles with whether they can go now; with `incidentId`: dispatchable first, then nearest. */
export function listVehicles(client: ApiClient, query: VehicleQuery = {}, signal?: AbortSignal): Promise<VehicleOut[]> {
  const params = new URLSearchParams();
  if (query.incidentId != null) params.set("incident_id", String(query.incidentId));
  for (const t of query.type ?? []) params.append("type", t);
  if (query.availableOnly) params.set("available_only", "true");
  const qs = params.toString();
  return client.get<VehicleOut[]>(`${API_PREFIX}/vehicles${qs ? `?${qs}` : ""}`, { auth: true, signal });
}

/** The only way a vehicle is sent. Resolves only on 201; a 409 carries `vehicle_locked` /
 * `vehicle_unavailable` (with `next_best`) or `incident_not_dispatchable` in the ApiError. */
export function dispatchIncident(client: ApiClient, incidentId: number, body: DispatchIn): Promise<AssignmentOut[]> {
  return client.post<AssignmentOut[]>(`${API_PREFIX}/incidents/${encodeURIComponent(String(incidentId))}/dispatch`, body, { auth: true });
}

// ---------------------------------------------------------------- assignment lifecycle (B1-A1-26)
export type HospitalOut = Schemas["HospitalOut"];

export function listHospitals(client: ApiClient, signal?: AbortSignal): Promise<HospitalOut[]> {
  return client.get<HospitalOut[]>(`${API_PREFIX}/hospitals`, { auth: true, signal });
}

/** Dispatcher stops an open assignment; the vehicle is free again. */
export function cancelAssignment(client: ApiClient, assignmentId: number, reason: string | null): Promise<AssignmentOut> {
  return client.post<AssignmentOut>(`${API_PREFIX}/assignments/${encodeURIComponent(String(assignmentId))}/cancel`,
    { reason }, { auth: true });
}

/** Dispatcher sends an open assignment to another hospital. */
export function changeHospital(client: ApiClient, assignmentId: number, hospitalId: number): Promise<AssignmentOut> {
  return client.request<AssignmentOut>("PATCH", `${API_PREFIX}/assignments/${encodeURIComponent(String(assignmentId))}/hospital`,
    { body: { hospital_id: hospitalId }, auth: true });
}
