// Idle sign-out (SRS NFR-C4, D-023): 30 minutes without the user touching the page signs them out,
// with a warning 2 minutes before. Only the user's own input counts: background refreshes (F4) keep
// the server session alive, so the browser must decide. The SRS default is used until the dashboard
// can read the `idle_logout_min` setting (admin settings API, B1-A1-31).
import { useCallback, useEffect, useRef, useState } from "react";

export const IDLE_LOGOUT_MIN = 30;
export const IDLE_WARNING_MIN = 2;
/** While the user is active, tell the server this often (the server ends sessions with no requests). */
export const KEEP_ALIVE_MIN = 5;
export const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart", "scroll"] as const;

interface Options {
  enabled: boolean;
  onIdle: () => void;
  /** Called every `keepAliveMs` if the user did something since the last call. */
  onKeepAlive?: () => void;
  logoutAfterMs?: number;
  warnBeforeMs?: number;
  keepAliveMs?: number;
  target?: Pick<Window, "addEventListener" | "removeEventListener">;
}

export function useIdleTimer({
  enabled,
  onIdle,
  onKeepAlive,
  logoutAfterMs = IDLE_LOGOUT_MIN * 60_000,
  warnBeforeMs = IDLE_WARNING_MIN * 60_000,
  keepAliveMs = KEEP_ALIVE_MIN * 60_000,
  target = window,
}: Options) {
  const [warning, setWarning] = useState(false);
  const warnTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const idleTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const onIdleRef = useRef(onIdle);
  onIdleRef.current = onIdle;
  const onKeepAliveRef = useRef(onKeepAlive);
  onKeepAliveRef.current = onKeepAlive;
  const activeSinceKeepAlive = useRef(false);

  const stop = useCallback(() => {
    clearTimeout(warnTimer.current);
    clearTimeout(idleTimer.current);
  }, []);

  const restart = useCallback(() => {
    stop();
    setWarning(false);
    warnTimer.current = setTimeout(() => setWarning(true), Math.max(0, logoutAfterMs - warnBeforeMs));
    idleTimer.current = setTimeout(() => {
      setWarning(false);
      onIdleRef.current();
    }, logoutAfterMs);
  }, [stop, logoutAfterMs, warnBeforeMs]);

  useEffect(() => {
    if (!enabled) {
      stop();
      setWarning(false);
      return;
    }
    restart();
    let last = 0;
    const onActivity = () => {
      const now = Date.now();
      if (now - last < 1000) return; // pointermove fires very often; once a second is enough
      last = now;
      activeSinceKeepAlive.current = true;
      restart();
    };
    const keepAlive = setInterval(() => {
      if (!activeSinceKeepAlive.current) return;
      activeSinceKeepAlive.current = false;
      onKeepAliveRef.current?.();
    }, keepAliveMs);
    for (const name of ACTIVITY_EVENTS) target.addEventListener(name, onActivity, { passive: true });
    return () => {
      stop();
      clearInterval(keepAlive);
      for (const name of ACTIVITY_EVENTS) target.removeEventListener(name, onActivity);
    };
  }, [enabled, restart, stop, target, keepAliveMs]);

  return { warning, stayActive: restart };
}
