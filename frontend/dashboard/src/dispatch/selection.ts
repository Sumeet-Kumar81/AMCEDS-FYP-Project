// Which vehicles the panel ticks for the dispatcher, and why a vehicle cannot be ticked (B1-A3-08).
import type { IncidentDetailOut, MessageKey, RecommendationOut, Translate, VehicleOut } from "@amceds/shared";

/** Reason key a vehicle cannot take an assignment now, or null when it can. */
export function blockReason(v: VehicleOut | undefined): { key: MessageKey; vars?: Record<string, string> } | null {
  if (!v) return null; // availability not known (vehicle list not loaded): the server still decides
  if (v.can_dispatch) return null;
  if (v.has_open_assignment) return { key: "dsp.reason.locked" };
  if (v.status !== "available") return { key: "dsp.reason.status", vars: { status: v.status } };
  if (v.driver_id == null) return { key: "dsp.reason.no_driver" };
  return { key: "dsp.reason.driver_off_duty" };
}

export function reasonText(t: Translate, v: VehicleOut | undefined): string | null {
  const r = blockReason(v);
  return r ? t(r.key, r.vars) : null;
}

/** The server's refusal reasons ("driver_off_duty", "status_en_route", …) in words. */
export function serverReasonText(t: Translate, reason: string): string {
  if (reason.startsWith("status_")) return t("dsp.reason.status", { status: reason.slice(7) });
  const key = `dsp.reason.${reason}` as MessageKey;
  return t(key) === key ? reason : t(key);
}

/**
 * Preselect what the AI says is needed: per vehicle type, as many of the top-ranked non-spare
 * recommendations as `allocation_summary.needed` asks for, skipping vehicles that cannot go now.
 * Nothing is preselected for an incident that already has vehicles (a backup is the dispatcher's call).
 */
export function preselect(incident: IncidentDetailOut, vehicles: Map<number, VehicleOut>): Set<number> {
  const recs: RecommendationOut[] = [...(incident.recommendations ?? [])].sort((a, b) => a.rank - b.rank);
  if (!recs.length || (incident.assignments ?? []).length > 0) return new Set();
  const needed = (incident.allocation_summary as { needed?: Record<string, number> } | null)?.needed ?? {};
  const wanted: Record<string, number> = Object.keys(needed).length ? { ...needed } : { [recs[0]!.vehicle_type]: 1 };
  const picked = new Set<number>();
  for (const r of recs) {
    if (r.is_spare || (wanted[r.vehicle_type] ?? 0) <= 0) continue;
    if (blockReason(vehicles.get(r.vehicle_id))) continue;
    picked.add(r.vehicle_id);
    wanted[r.vehicle_type] = (wanted[r.vehicle_type] ?? 0) - 1;
  }
  return picked;
}

/** Same rule as the server's audit `same_as_ai`: every chosen vehicle is one the AI recommended. */
export function differsFromAi(incident: IncidentDetailOut, chosen: Set<number>): boolean {
  const recommended = new Set((incident.recommendations ?? []).map((r) => r.vehicle_id));
  return recommended.size === 0 || [...chosen].some((id) => !recommended.has(id));
}
