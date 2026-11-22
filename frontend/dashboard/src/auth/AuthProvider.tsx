// Dashboard sign-in state (B1-A3-04; SRS UC-11 1, 1a, 1b, 3; NFR-C2, NFR-C4; TC-32).
// Tokens stay in the API client's memory store (never in browser storage), so a page reload means
// signing in again. Drivers are signed out at once: their work is in the mobile app.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiClient, getMe, login as apiLogin, logout as apiLogout, type MeOut, type UserRole } from "@amceds/shared";

/** Why the user is on the login page (shown there once). */
export type SignOutReason = "signed_out" | "session_ended" | "idle";

export const DASHBOARD_ROLES: ReadonlySet<UserRole> = new Set(["dispatcher", "admin"]);

/** Thrown by `signIn` when a driver account tries the dashboard. */
export class DriverNotAllowedError extends Error {
  constructor() {
    super("drivers use the mobile app");
    this.name = "DriverNotAllowedError";
  }
}

interface AuthValue {
  user: MeOut | null;
  notice: SignOutReason | null;
  signIn: (username: string, password: string) => Promise<MeOut>;
  signOut: (reason?: SignOutReason) => Promise<void>;
  clearNotice: () => void;
  client: ApiClient;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ client, children }: { client: ApiClient; children: ReactNode }) {
  const [user, setUser] = useState<MeOut | null>(null);
  const [notice, setNotice] = useState<SignOutReason | null>(null);
  const userRef = useRef<MeOut | null>(null);
  const leaving = useRef(false); // true while we end the session ourselves

  const setSignedIn = useCallback((me: MeOut | null) => {
    userRef.current = me;
    setUser(me);
  }, []);

  // The client clears its tokens when the server ends the session (or a refresh fails).
  useEffect(
    () =>
      client.tokens.subscribe((tokens) => {
        if (tokens === null && userRef.current && !leaving.current) {
          setSignedIn(null);
          setNotice("session_ended");
        }
      }),
    [client, setSignedIn],
  );

  const signOut = useCallback(
    async (reason: SignOutReason = "signed_out") => {
      leaving.current = true;
      try {
        if (client.tokens.get()) await apiLogout(client).catch(() => undefined); // tokens are cleared anyway
      } finally {
        leaving.current = false;
        setSignedIn(null);
        setNotice(reason);
      }
    },
    [client, setSignedIn],
  );

  const signIn = useCallback(
    async (username: string, password: string) => {
      setNotice(null);
      await apiLogin(client, { username, password });
      let me: MeOut;
      try {
        me = await getMe(client);
      } catch (error) {
        leaving.current = true;
        client.tokens.clear();
        leaving.current = false;
        throw error;
      }
      if (!DASHBOARD_ROLES.has(me.role)) {
        leaving.current = true;
        await apiLogout(client).catch(() => undefined);
        leaving.current = false;
        throw new DriverNotAllowedError();
      }
      setSignedIn(me);
      return me;
    },
    [client, setSignedIn],
  );

  const value = useMemo<AuthValue>(
    () => ({ user, notice, signIn, signOut, clearNotice: () => setNotice(null), client }),
    [user, notice, signIn, signOut, client],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}

/** Where each role starts. */
export function homeFor(role: UserRole): string {
  return role === "admin" ? "/admin" : "/queue";
}
