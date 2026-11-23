// Report form rules (B1-A3-03). They mirror backend/app/schemas/report.py (ReportIn) so most mistakes
// are caught before sending; the server still checks everything and its 422 is shown per field.
import type { ReportIn, MessageKey, ValidationIssue } from "@amceds/shared";

export const LIMITS = { description: 2000, address: 500, name: 100 } as const;
/** Same rule as the backend's PHONE_PATTERN (D-036): 11 digits starting with 03, after removing spaces and dashes. */
export const PHONE_PATTERN = /^03[0-9]{9}$/;

/** The phone as it is checked and sent: spaces and dashes removed ("0300 123-4567" -> "03001234567"). */
export function phoneDigits(phone: string): string {
  return phone.replace(/[\s-]/g, "");
}

export interface GpsFix {
  lat: number;
  lon: number;
  accuracy: number | null; // metres
}

export interface ReportDraft {
  description: string;
  addressText: string;
  name: string;
  phone: string;
  gps: GpsFix | null;
}

export type Field = "description" | "addressText" | "name" | "phone" | "location";

export interface FieldError {
  key?: MessageKey;
  vars?: Record<string, string | number>;
  /** A server message, shown as is when the server found a problem this page did not. */
  text?: string;
}

export type FieldErrors = Partial<Record<Field, FieldError>>;

export const EMPTY_DRAFT: ReportDraft = { description: "", addressText: "", name: "", phone: "", gps: null };

export function validate(draft: ReportDraft): FieldErrors {
  const errors: FieldErrors = {};
  const description = draft.description.trim();
  if (!description) errors.description = { key: "report.err_description_required" };
  else if (description.length > LIMITS.description) {
    errors.description = { key: "report.err_too_long", vars: { max: LIMITS.description } };
  }
  // D-036: place, name and phone are required.
  const address = draft.addressText.trim();
  if (!address) errors.addressText = { key: "report.err_address_required" };
  else if (address.length > LIMITS.address) errors.addressText = { key: "report.err_too_long", vars: { max: LIMITS.address } };
  const name = draft.name.trim();
  if (!name) errors.name = { key: "report.err_name_required" };
  else if (name.length > LIMITS.name) errors.name = { key: "report.err_too_long", vars: { max: LIMITS.name } };
  const phone = phoneDigits(draft.phone);
  if (!phone) errors.phone = { key: "report.err_phone_required" };
  else if (!PHONE_PATTERN.test(phone)) errors.phone = { key: "report.err_phone" };
  return errors;
}

/** The request body: trimmed text, the phone as 11 digits, coordinates only from GPS. */
export function toReportIn(draft: ReportDraft, clientRequestId: string): ReportIn {
  const body: ReportIn = {
    description: draft.description.trim(), channel: "web", client_request_id: clientRequestId,
    address_text: draft.addressText.trim(), reporter_name: draft.name.trim(), reporter_phone: phoneDigits(draft.phone),
  };
  if (draft.gps) {
    body.lat = draft.gps.lat;
    body.lon = draft.gps.lon;
  }
  return body;
}

const SERVER_FIELDS: Record<string, Field> = {
  description: "description",
  address_text: "addressText",
  reporter_name: "name",
  reporter_phone: "phone",
  lat: "location",
  lon: "location",
};

/** Puts each problem of a server 422 under its field (body-level problems go to the location). */
export function serverFieldErrors(issues: ValidationIssue[]): FieldErrors {
  const errors: FieldErrors = {};
  for (const issue of issues) {
    const name = issue.loc.length > 1 ? String(issue.loc[issue.loc.length - 1]) : "";
    const field = SERVER_FIELDS[name] ?? (issue.loc.length <= 1 ? "location" : "description");
    errors[field] ??= { text: issue.msg.replace(/^Value error, /, "") };
  }
  return errors;
}

/** True when the visible report changed, so a new submission id is needed. */
export function sameDraft(a: ReportDraft, b: ReportDraft): boolean {
  return (
    a.description.trim() === b.description.trim() &&
    a.addressText.trim() === b.addressText.trim() &&
    a.name.trim() === b.name.trim() &&
    phoneDigits(a.phone) === phoneDigits(b.phone) &&
    a.gps?.lat === b.gps?.lat &&
    a.gps?.lon === b.gps?.lon
  );
}

/** A random id per submission (TC-04). crypto.randomUUID needs a secure page; fall back to random bytes. */
export function newRequestId(cryptoImpl: Pick<Crypto, "getRandomValues"> & Partial<Pick<Crypto, "randomUUID">> = crypto): string {
  if (typeof cryptoImpl.randomUUID === "function") {
    try {
      return cryptoImpl.randomUUID();
    } catch {
      // not a secure context (for example http://192.168.x.x): use random bytes below
    }
  }
  const bytes = cryptoImpl.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
