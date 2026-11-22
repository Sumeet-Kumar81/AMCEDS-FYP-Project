// Error handling for every API call (contract C-4 §1.1): the backend always answers 4xx/5xx with
// `{code, message, details}`. Anything else (no network, a proxy page, a timeout) is mapped to a
// client-side code so screens can always show a clear message.
import type { components } from "./schema";

export type ErrorBody = components["schemas"]["ErrorBody"];

/** One entry of `details` for a 422 `validation_error` (the submitted value is never echoed). */
export interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** Codes made on this side, never sent by the backend. */
export const CLIENT_CODES = {
  network: "network_error", // no answer at all (offline, server down, CORS)
  timeout: "timeout",
  badResponse: "bad_response", // an error without the contract body
} as const;

export class ApiError extends Error {
  readonly status: number; // HTTP status, 0 when there was no answer
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** The database is down: nothing was saved (a report never gets a reference number). */
  get serviceUnavailable(): boolean {
    return this.status === 503;
  }

  /** No answer from the server (network, timeout). */
  get noConnection(): boolean {
    return this.status === 0;
  }

  /** In the contract but not built yet (501): never shown as success. */
  get notImplemented(): boolean {
    return this.status === 501;
  }

  /** The field problems of a 422, or an empty list. */
  get validationIssues(): ValidationIssue[] {
    if (this.status !== 422 || !Array.isArray(this.details)) return [];
    return this.details.filter(
      (d): d is ValidationIssue => typeof d === "object" && d !== null && "msg" in d && "loc" in d,
    );
  }
}

function isErrorBody(value: unknown): value is ErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as ErrorBody).code === "string" &&
    typeof (value as ErrorBody).message === "string"
  );
}

/** Builds an ApiError from a failed HTTP answer; `body` is the parsed JSON or the raw text. */
export function toApiError(status: number, body: unknown): ApiError {
  if (isErrorBody(body)) return new ApiError(status, body.code, body.message, body.details ?? null);
  return new ApiError(status, CLIENT_CODES.badResponse, `The server answered HTTP ${status} without an error body.`);
}
