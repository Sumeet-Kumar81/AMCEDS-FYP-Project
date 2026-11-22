// Dispatch approval panel (B1-A3-08; SRS UC-06 3–4, 3a, 4a; NFR-P14, NFR-S1; TC-19…22, TC-51).
// The needed vehicles are preticked; Approve opens a summary; only Confirm sends the request — so a
// recommended dispatch is three clicks (open incident, Approve, Confirm) and nothing is sent without
// Confirm. A 409 shows which vehicle could not go and offers the next best. Success is shown only after
// the server answered 201. Drivers are not alerted automatically yet, so the screen says so.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  ApproximateEtaTag,
  ErrorState,
  dispatchIncident,
  listHospitals,
  listVehicles,
  useErrorText,
  useI18n,
  type IncidentDetailOut,
  type VehicleOut,
} from "@amceds/shared";
import { useAuth } from "../auth/AuthProvider";
import { vehicleText } from "../incidents/labels";
import { blockReason, differsFromAi, openAssignments, preselect, reasonText, serverReasonText } from "./selection";

export const VEHICLES_REFRESH_MS = 10_000;

type Problem =
  | { kind: "locked"; ids: number[]; next: number[] }
  | { kind: "unavailable"; list: { vehicle_id: number; reason: string }[]; next: number[] }
  | { kind: "not_dispatchable"; status: string }
  | { kind: "other"; text: string };

function problemFrom(error: unknown, text: (e: unknown) => string): Problem {
  if (error instanceof ApiError && error.status === 409) {
    const d = (error.details ?? {}) as Record<string, unknown>;
    const next = Array.isArray(d.next_best) ? (d.next_best as number[]) : [];
    if (error.code === "vehicle_locked") return { kind: "locked", ids: (d.vehicle_ids as number[]) ?? [], next };
    if (error.code === "vehicle_unavailable") {
      return { kind: "unavailable", list: (d.vehicles as { vehicle_id: number; reason: string }[]) ?? [], next };
    }
    if (error.code === "incident_not_dispatchable") return { kind: "not_dispatchable", status: String(d.status ?? "") };
  }
  return { kind: "other", text: text(error) };
}

const FINAL = new Set(["fake", "closed"]);

export function DispatchPanel({ incident }: { incident: IncidentDetailOut }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const { client } = useAuth();
  const queries = useQueryClient();
  const id = incident.incident_id;

  const vehiclesQ = useQuery({
    queryKey: ["vehicles", id],
    queryFn: ({ signal }) => listVehicles(client, { incidentId: id }, signal),
    refetchInterval: VEHICLES_REFRESH_MS,
    enabled: !FINAL.has(incident.status),
  });
  const byId = useMemo(() => new Map((vehiclesQ.data ?? []).map((v) => [v.vehicle_id, v])), [vehiclesQ.data]);
  const plate = (vid: number) => byId.get(vid)?.plate_number
    ?? (incident.recommendations ?? []).find((r) => r.vehicle_id === vid)?.plate_number ?? `#${vid}`;

  const hospitalsQ = useQuery({ queryKey: ["hospitals"], queryFn: ({ signal }) => listHospitals(client, signal),
    enabled: !FINAL.has(incident.status), staleTime: 60_000 });
  const [hospitalId, setHospitalId] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const initialised = useRef(false);
  useEffect(() => {
    if (initialised.current || !vehiclesQ.data) return;
    initialised.current = true;
    setSelected(preselect(incident, byId));
  }, [vehiclesQ.data, byId, incident]);

  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [done, setDone] = useState<string[] | null>(null);
  const inFlight = useRef(false);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const approveRef = useRef<HTMLButtonElement>(null);

  const mutation = useMutation({
    mutationFn: (vehicleIds: number[]) =>
      dispatchIncident(client, id, { vehicle_ids: vehicleIds, override_reason: reason.trim() || null,
        hospital_id: hospitalId ? Number(hospitalId) : null }),
  });

  useEffect(() => {
    if (open) confirmRef.current?.focus();
  }, [open]);

  if (FINAL.has(incident.status)) {
    return <p className="inc-alert" role="note">{t("dsp.not_dispatchable", { status: incident.status })}</p>;
  }

  const recs = [...(incident.recommendations ?? [])].sort((a, b) => a.rank - b.rank);
  const recIds = new Set(recs.map((r) => r.vehicle_id));
  const others = (vehiclesQ.data ?? []).filter((v) => !recIds.has(v.vehicle_id));
  const manual = recs.length === 0;
  const vehicleOnTheWay = openAssignments(incident).length > 0;
  const chosen = [...selected];
  const differs = differsFromAi(incident, selected);

  const toggle = (vid: number) => setSelected((s) => {
    const next = new Set(s);
    if (next.has(vid)) next.delete(vid); else next.add(vid);
    return next;
  });

  function close() {
    if (inFlight.current) return;
    setOpen(false);
    setProblem(null);
    approveRef.current?.focus();
  }

  async function confirm() {
    if (inFlight.current || chosen.length === 0) return; // one request per press
    inFlight.current = true;
    setProblem(null);
    try {
      await mutation.mutateAsync(chosen);
      setDone(chosen.map(plate));
      setOpen(false);
      setSelected(new Set());
      setReason("");
      setHospitalId("");
      await Promise.all([
        queries.invalidateQueries({ queryKey: ["incident", id] }),
        queries.invalidateQueries({ queryKey: ["incidents"] }),
        queries.invalidateQueries({ queryKey: ["vehicles", id] }),
      ]);
    } catch (error) {
      setProblem(problemFrom(error, errorText));
      void queries.invalidateQueries({ queryKey: ["vehicles", id] });
    } finally {
      inFlight.current = false;
    }
  }

  function swapIn(failing: number[], replacement: number) {
    setSelected((s) => new Set([...[...s].filter((x) => !failing.includes(x)), replacement]));
    setProblem(null);
  }

  const signalLost = chosen.filter((vid) => byId.get(vid)?.signal_lost).map(plate);
  const sending = mutation.isPending;

  const row = (vid: number, cells: ReactNode, testId: string) => {
    const v = byId.get(vid);
    const blocked = blockReason(v);
    return (
      <tr key={vid} data-testid={testId} className={blocked ? "dsp-blocked" : undefined}>
        <td>
          <input type="checkbox" aria-label={`${t("dsp.col_pick")} ${plate(vid)}`} checked={selected.has(vid)}
            disabled={(!!blocked && !selected.has(vid)) || sending} onChange={() => toggle(vid)} />
        </td>
        {cells}
        <td className="dsp-note">
          {blocked && <span className="dsp-reason">{t("dsp.unavailable")}: {reasonText(t, v)}</span>}
          {v?.signal_lost && !blocked && <span className="q-muted">📡 {t("dsp.signal_lost")}</span>}
        </td>
      </tr>
    );
  };

  return (
    <div className="dsp">
      {done && (
        <div className="dsp-done" role="status">
          <p><strong>✔ {t("dsp.done", { plates: done.join(", ") })}</strong></p>
          <p className="dsp-call">☎ {t("dsp.call_driver")}</p>
        </div>
      )}
      {vehicleOnTheWay && <p className="q-muted">{t("dsp.backup")}</p>}
      {manual && <p className="inc-warn" data-testid="manual-mode">🛠 {t("dsp.manual")}</p>}
      {vehiclesQ.isError && <ErrorState error={vehiclesQ.error} onRetry={() => void vehiclesQ.refetch()} />}

      {recs.length > 0 && (
        <table className="inc-recs">
          <thead>
            <tr>
              <th scope="col">{t("dsp.col_pick")}</th><th scope="col">{t("inc.col_rank")}</th><th scope="col">{t("inc.col_vehicle")}</th>
              <th scope="col">{t("inc.col_type")}</th><th scope="col">{t("inc.col_distance")}</th><th scope="col">{t("inc.col_eta")}</th>
              <th scope="col"><span className="sr-only">status</span></th>
            </tr>
          </thead>
          <tbody>
            {recs.map((r) => row(r.vehicle_id, <>
              <td>{r.rank}</td>
              <td dir="ltr">{r.plate_number ?? `#${r.vehicle_id}`}{r.is_spare && <span className="inc-spare"> ({t("inc.spare")})</span>}</td>
              <td>{vehicleText(t, r.vehicle_type)}</td>
              <td>{t("inc.km", { km: (r.distance_meters / 1000).toFixed(1) })}</td>
              <td>{t("inc.min", { min: Math.max(1, Math.round(r.eta_seconds / 60)) })} <ApproximateEtaTag approximate={r.eta_is_approximate} /></td>
            </>, "rec-row"))}
          </tbody>
        </table>
      )}

      <details className="dsp-other" open={manual || undefined}>
        <summary>{t("dsp.other")}</summary>
        <p className="q-muted">{t("dsp.other_hint")}</p>
        {vehiclesQ.data && others.length === 0 && <p className="q-muted">{t("dsp.no_other")}</p>}
        {others.length > 0 && (
          <table className="inc-recs">
            <tbody>
              {others.map((v: VehicleOut) => row(v.vehicle_id, <>
                <td dir="ltr">{v.plate_number}</td>
                <td>{vehicleText(t, v.vehicle_type)}</td>
                <td>{v.distance_meters != null ? <>{t("inc.km", { km: (v.distance_meters / 1000).toFixed(1) })} <ApproximateEtaTag approximate /></> : "—"}</td>
                <td>{v.driver_name ?? ""}</td>
              </>, "other-row"))}
            </tbody>
          </table>
        )}
      </details>

      <div className="dsp-hospital">
        <label htmlFor="dsp-hospital">{t("dsp.hospital_label")}</label>
        <select id="dsp-hospital" value={hospitalId} onChange={(e) => setHospitalId(e.target.value)} disabled={sending}>
          <option value="">{t("dsp.hospital_none")}</option>
          {(hospitalsQ.data ?? []).map((h) => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
        </select>
      </div>
      <div className="inc-approve">
        <button ref={approveRef} type="button" className="dsp-approve" disabled={chosen.length === 0 || sending}
          onClick={() => { setProblem(null); setOpen(true); }}>
          {t("dsp.approve")}
        </button>
        {chosen.length === 0 && <p className="q-muted">{t("dsp.choose_first")}</p>}
      </div>

      {open && (
        <div className="dsp-backdrop">
          <div className="dsp-dialog" role="dialog" aria-modal="true" aria-labelledby="dsp-title"
            onKeyDown={(e) => { if (e.key === "Escape") close(); }}>
            <h3 id="dsp-title">{t("dsp.summary_title")}</h3>
            <p dir="auto">{t("dsp.summary_incident", { ref: incident.reference_no, severity: incident.severity ?? t("severity.unknown") })}</p>
            <p>{t("dsp.summary_vehicles")}</p>
            <ul data-testid="summary-vehicles">
              {chosen.map((vid) => (
                <li key={vid} dir="ltr">{plate(vid)}{byId.get(vid) ? ` — ${vehicleText(t, byId.get(vid)!.vehicle_type)}` : ""}</li>
              ))}
            </ul>
            {hospitalId && (
              <p>{t("dsp.summary_hospital", { name: hospitalsQ.data?.find((h) => String(h.hospital_id) === hospitalId)?.name ?? hospitalId })}</p>
            )}
            {manual && <p className="inc-warn">{t("dsp.warn_manual")}</p>}
            {incident.trust_tier === "low" && <p className="inc-warn">{t("dsp.warn_low_trust")}</p>}
            {signalLost.length > 0 && <p className="inc-warn">{t("dsp.warn_signal", { plates: signalLost.join(", ") })}</p>}
            {differs && !manual && (
              <>
                <p className="inc-warn">{t("dsp.differs")}</p>
                <label htmlFor="dsp-reason">{t("dsp.reason_label")}</label>
                <textarea id="dsp-reason" dir="auto" rows={2} maxLength={500} value={reason}
                  onChange={(e) => setReason(e.target.value)} disabled={sending} />
              </>
            )}

            {problem && (
              <div className="inc-alert" role="alert" data-testid="dispatch-problem">
                {problem.kind === "locked" && <p>{t("dsp.err_locked", { plates: problem.ids.map(plate).join(", ") })}</p>}
                {problem.kind === "unavailable" && (
                  <p>{t("dsp.err_unavailable", { list: problem.list.map((x) => `${plate(x.vehicle_id)}: ${serverReasonText(t, x.reason)}`).join("; ") })}</p>
                )}
                {problem.kind === "not_dispatchable" && <p>{t("dsp.err_not_dispatchable", { status: problem.status })}</p>}
                {problem.kind === "other" && <p>{t("dsp.err_other", { text: problem.text })}</p>}
                {(problem.kind === "locked" || problem.kind === "unavailable") && (
                  problem.next.length > 0 ? (
                    <div className="dsp-next">
                      {problem.next.map((vid) => (
                        <button key={vid} type="button" onClick={() => swapIn(
                          problem.kind === "locked" ? problem.ids : problem.list.map((x) => x.vehicle_id), vid)}>
                          {t("dsp.use_instead", { plate: plate(vid) })}
                        </button>
                      ))}
                    </div>
                  ) : <p>{t("dsp.no_next_best")}</p>
                )}
              </div>
            )}

            <div className="dsp-actions">
              <button ref={confirmRef} type="button" className="dsp-confirm" onClick={() => void confirm()}
                disabled={sending || chosen.length === 0 || problem?.kind === "not_dispatchable"}>
                {sending ? t("dsp.sending") : t("dsp.confirm")}
              </button>
              <button type="button" onClick={close} disabled={sending}>{t("dsp.cancel")}</button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
