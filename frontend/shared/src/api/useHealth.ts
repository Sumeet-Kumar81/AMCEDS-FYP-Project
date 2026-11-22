// Polls GET /health so every app can show the service banner (NFR-S5). The WebSocket
// `system.service_status` event replaces this once the hub exists (B1-A1-29, B1-A3-05).
import { useEffect, useState } from "react";
import type { ApiClient } from "./client";
import { downServices, getHealth, type HealthOut } from "./endpoints";
import { ApiError } from "./errors";

export interface HealthState {
  health: HealthOut | null;
  down: string[];
  unreachable: boolean;
  checked: boolean;
}

export const HEALTH_POLL_MS = 15_000;

export function useHealth(client: ApiClient, intervalMs: number = HEALTH_POLL_MS): HealthState {
  const [state, setState] = useState<HealthState>({ health: null, down: [], unreachable: false, checked: false });

  useEffect(() => {
    const controller = new AbortController();
    const check = async () => {
      try {
        const health = await getHealth(client, controller.signal);
        setState({ health, down: downServices(health), unreachable: false, checked: true });
      } catch (error) {
        if (controller.signal.aborted) return;
        const unreachable = !(error instanceof ApiError) || error.noConnection || error.status >= 500;
        setState({ health: null, down: [], unreachable, checked: true });
      }
    };
    void check();
    const timer = setInterval(check, intervalMs);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [client, intervalMs]);

  return state;
}
