// Thin fetch wrapper used by every screen (B1-A3-01):
// - base URL from VITE_API_URL, JSON in and out, a timeout on every call;
// - adds `Authorization: Bearer <access token>` to private calls;
// - on 401 for a private call, refreshes the session once (shared by parallel calls) and retries;
//   if refreshing fails the tokens are cleared and `onSessionEnded` is called (screen goes to login);
// - 503 calls `onServiceUnavailable` (service banner) and is still thrown to the caller;
// - every failure is an ApiError with the backend's `{code, message, details}`.
import { ApiError, CLIENT_CODES, toApiError } from "./errors";
import type { components } from "./schema";
import { TokenStore } from "./tokens";

type TokenOut = components["schemas"]["TokenOut"];

export const API_PREFIX = "/api/v1";
export const DEFAULT_TIMEOUT_MS = 15_000;

export interface ApiClientOptions {
  baseUrl: string;
  tokens?: TokenStore;
  timeoutMs?: number;
  fetch?: typeof fetch;
  onSessionEnded?: (error: ApiError) => void;
  onServiceUnavailable?: (error: ApiError) => void;
}

export interface RequestOptions {
  body?: unknown;
  /** Send the access token and refresh on 401. Default: true when a token store exists. */
  auth?: boolean;
  signal?: AbortSignal;
}

export type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export class ApiClient {
  readonly baseUrl: string;
  readonly tokens: TokenStore;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;
  private readonly onSessionEnded?: (error: ApiError) => void;
  private readonly onServiceUnavailable?: (error: ApiError) => void;
  private refreshing: Promise<boolean> | null = null;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.tokens = options.tokens ?? new TokenStore();
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.fetchImpl = options.fetch ?? ((...args) => globalThis.fetch(...args));
    this.onSessionEnded = options.onSessionEnded;
    this.onServiceUnavailable = options.onServiceUnavailable;
  }

  async request<T>(method: Method, path: string, options: RequestOptions = {}): Promise<T> {
    const auth = options.auth ?? this.tokens.get() !== null;
    try {
      return await this.send<T>(method, path, options, auth);
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401 || !auth) throw error;
      if (!(await this.refreshSession())) {
        this.tokens.clear();
        this.onSessionEnded?.(error);
        throw error;
      }
      try {
        return await this.send<T>(method, path, options, auth);
      } catch (retryError) {
        if (retryError instanceof ApiError && retryError.status === 401) {
          this.tokens.clear();
          this.onSessionEnded?.(retryError);
        }
        throw retryError;
      }
    }
  }

  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("GET", path, options);
  }

  post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("POST", path, { ...options, body });
  }

  /** One refresh at a time; parallel 401s wait for the same attempt. */
  private refreshSession(): Promise<boolean> {
    const current = this.tokens.get();
    if (!current) return Promise.resolve(false);
    if (!this.refreshing) {
      this.refreshing = this.send<TokenOut>("POST", `${API_PREFIX}/auth/refresh`,
        { body: { refresh_token: current.refreshToken } }, false)
        .then((out) => {
          this.tokens.set({ accessToken: out.access_token, refreshToken: out.refresh_token });
          return true;
        })
        .catch(() => false)
        .finally(() => {
          this.refreshing = null;
        });
    }
    return this.refreshing;
  }

  private async send<T>(method: Method, path: string, options: RequestOptions, auth: boolean): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    const token = this.tokens.get()?.accessToken;
    if (auth && token) headers.Authorization = `Bearer ${token}`;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(new DOMException("timeout", "TimeoutError")), this.timeoutMs);
    const onAbort = () => controller.abort(options.signal?.reason);
    options.signal?.addEventListener("abort", onAbort, { once: true });

    let response: Response;
    try {
      response = await this.fetchImpl(this.baseUrl + path, {
        method,
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: controller.signal,
      });
    } catch (error) {
      if (options.signal?.aborted) throw error; // the screen cancelled it: not an API problem
      const timedOut = controller.signal.aborted;
      throw new ApiError(0, timedOut ? CLIENT_CODES.timeout : CLIENT_CODES.network,
        timedOut ? "The server took too long to answer." : "Could not reach the server.");
    } finally {
      clearTimeout(timer);
      options.signal?.removeEventListener("abort", onAbort);
    }

    const body = await readBody(response);
    if (!response.ok) {
      const error = toApiError(response.status, body);
      if (error.serviceUnavailable) this.onServiceUnavailable?.(error);
      throw error;
    }
    return body as T;
  }
}

async function readBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** The API address for the apps: VITE_API_URL, else the local backend. */
export function apiBaseUrl(env: Record<string, string | undefined> = import.meta.env ?? {}): string {
  return (env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");
}
