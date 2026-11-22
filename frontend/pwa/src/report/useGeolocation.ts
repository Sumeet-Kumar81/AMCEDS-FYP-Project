// Browser GPS for the report page (UC-01 2a). Refusal or failure never blocks a report: the page then
// asks for a place name or landmark, and with neither the report is sent with location "unknown" (TC-03).
import { useCallback, useEffect, useRef, useState } from "react";
import type { GpsFix } from "./validation";

export type GeoStatus = "idle" | "locating" | "ok" | "denied" | "unavailable" | "unsupported";

export const GEO_OPTIONS: PositionOptions = { enableHighAccuracy: true, timeout: 15_000, maximumAge: 60_000 };

export function useGeolocation(geo: Geolocation | undefined = globalThis.navigator?.geolocation) {
  const [status, setStatus] = useState<GeoStatus>("idle");
  const [fix, setFix] = useState<GpsFix | null>(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const request = useCallback(() => {
    if (!geo) {
      setStatus("unsupported");
      return;
    }
    setStatus("locating");
    geo.getCurrentPosition(
      (pos) => {
        if (!alive.current) return;
        setFix({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          accuracy: Number.isFinite(pos.coords.accuracy) ? Math.round(pos.coords.accuracy) : null,
        });
        setStatus("ok");
      },
      (err) => {
        if (!alive.current) return;
        setFix(null);
        setStatus(err.code === 1 ? "denied" : "unavailable"); // 1 PERMISSION_DENIED; 2 unavailable, 3 timeout
      },
      GEO_OPTIONS,
    );
  }, [geo]);

  const clear = useCallback(() => {
    setFix(null);
    setStatus("idle");
  }, []);

  return { status, fix, request, clear };
}
