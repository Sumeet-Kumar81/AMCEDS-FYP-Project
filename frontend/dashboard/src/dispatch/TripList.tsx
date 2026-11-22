// Each dispatched vehicle and where its trip stands (B1-A3-07/08 follow-up for B1-A1-26; SRS UC-08, UC-09).
// The state comes from the assignment status and its timestamps; the incident is refreshed every 5 s, so
// what drivers report shows up here. Open assignments can be cancelled (with a confirmation) or sent to
// another hospital. A "no answer" warning after 60 s is only a reminder on this screen: the real
// answer timeout needs the scheduler (B1-A1-28, D-029). Drivers are not alerted yet, so every change says so.
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelAssignment,
  changeHospital,
  listHospitals,
  listVehicles,
  useErrorText,
  useI18n,
  type AssignmentOut,
  type IncidentDetailOut,
  type MessageKey,
  type Translate,
} from "@amceds/shared";
import { useAuth } from "../auth/AuthProvider";
import { clockTime, vehicleText } from "../incidents/labels";
import { OPEN_ASSIGNMENT } from "./selection";

/** SRS Appendix C: the driver should answer within 60 s. Used only for the on-screen reminder. */
export const ANSWER_LIMIT_S = 60;
const STEPS = ["approved_at", "accepted_at", "on_scene_at", "picked_up_at", "at_hospital_at", "completed_at", "declined_at"] as const;
type Stamp = (typeof STEPS)[number];
const STEP_KEY: Record<Stamp, MessageKey> = {
  approved_at: "trip.step.approved", accepted_at: "trip.step.accepted", on_scene_at: "trip.step.on_scene",
  picked_up_at: "trip.step.picked_up", at_hospital_at: "trip.step.at_hospital", completed_at: "trip.step.completed",
  declined_at: "trip.step.declined",
};

/** Where the trip stands, in words. */
export function tripState(t: Translate, a: AssignmentOut): string {
  switch (a.status) {
    case "accepted":
      if (a.at_hospital_at) return t("trip.state.at_hospital");
      if (a.picked_up_at) return t("trip.state.picked_up");
      if (a.on_scene_at) return t("trip.state.on_scene");
      return t("trip.state.accepted");
    case "declined": {
      const key = `decline.${a.decline_reason ?? "other"}` as MessageKey;
      return t("trip.state.declined", { reason: t(key) === key ? (a.decline_reason ?? "") : t(key) });
    }
    case "approved": case "completed": case "cancelled": case "timed_out":
      return t(`trip.state.${a.status}` as MessageKey);
    default:
      return a.status;
  }
}

function useNow(everyMs = 5_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(timer);
  }, [everyMs]);
  return now;
}

function TripCard({ a, plate, vtype, hospitalName, onDone }: {
  a: AssignmentOut; plate: string; vtype: string | null; hospitalName: (id: number | null | undefined) => string | null;
  onDone: (message: string) => void;
}) {
  const { t, lang } = useI18n();
  const errorText = useErrorText();
  const { client, user } = useAuth();
  const queries = useQueryClient();
  const now = useNow();
  const open = OPEN_ASSIGNMENT.has(a.status);
  const hospitals = useQuery({ queryKey: ["hospitals"], queryFn: ({ signal }) => listHospitals(client, signal),
    enabled: open, staleTime: 60_000 });

  const [editing, setEditing] = useState(false);
  const [hospitalId, setHospitalId] = useState<string>(a.hospital_id ? String(a.hospital_id) : "");
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  const [working, setWorking] = useState(false);
  const closeConfirm = () => { setConfirming(false); setReason(""); }; // a closed box forgets what was typed

  const refresh = () => Promise.all([
    queries.invalidateQueries({ queryKey: ["incident"] }),
    queries.invalidateQueries({ queryKey: ["incidents"] }),
    queries.invalidateQueries({ queryKey: ["vehicles"] }),
  ]);

  async function act(run: () => Promise<unknown>, message: string) {
    if (busy.current) return;
    busy.current = true;
    setWorking(true);
    setError(null);
    try {
      await run();
      setEditing(false);
      setConfirming(false);
      setReason("");
      onDone(message);
      await refresh();
    } catch (err) {
      setError(t("trip.err", { text: errorText(err) }));
    } finally {
      busy.current = false;
      setWorking(false);
    }
  }

  const waitingS = a.status === "approved" ? Math.floor((now - new Date(a.approved_at).getTime()) / 1000) : 0;
  const stamps = STEPS.filter((s) => a[s]);
  const who = a.approved_by === user?.user_id ? t("dsp.you") : t("dsp.user", { id: a.approved_by });
  const hName = hospitalName(a.hospital_id);
  const chosen = hospitals.data?.find((h) => String(h.hospital_id) === hospitalId);

  return (
    <li className={`trip trip-${a.status}`} data-testid="trip" data-assignment={a.assignment_id}>
      <div className="trip-head">
        <strong dir="ltr">{plate}</strong>
        {vtype && <span className="q-muted">{vehicleText(t, vtype)}</span>}
        <span className="trip-state" data-testid="trip-state">{tripState(t, a)}</span>
      </div>
      <p className="q-muted">{t("trip.approved_by", { time: clockTime(a.approved_at, lang), who })} · {hName ? t("trip.hospital", { name: hName }) : t("trip.no_hospital")}</p>
      <ol className="trip-steps" aria-label="timeline">
        {stamps.map((s) => <li key={s}>{t(STEP_KEY[s])} {clockTime(a[s]!, lang)}</li>)}
      </ol>
      {waitingS > ANSWER_LIMIT_S && (
        <p className="inc-warn" role="alert" data-testid="no-answer">⏱ {t("trip.no_answer", { minutes: Math.max(1, Math.floor(waitingS / 60)) })}</p>
      )}
      {error && <p className="inc-alert" role="alert">{error}</p>}

      {open && !editing && !confirming && (
        <div className="trip-actions">
          <button type="button" onClick={() => { setError(null); setEditing(true); }}>{t("trip.change_hospital")}</button>
          <button type="button" className="trip-cancel" onClick={() => { setError(null); setConfirming(true); }}>{t("trip.cancel")}</button>
        </div>
      )}

      {open && editing && (
        <div className="trip-actions">
          <label htmlFor={`trip-h-${a.assignment_id}`} className="sr-only">{t("trip.change_hospital")}</label>
          <select id={`trip-h-${a.assignment_id}`} value={hospitalId} onChange={(e) => setHospitalId(e.target.value)} disabled={working}>
            <option value="">{t("dsp.hospital_none")}</option>
            {(hospitals.data ?? []).map((h) => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
          </select>
          <button type="button" disabled={working || !hospitalId || Number(hospitalId) === a.hospital_id}
            onClick={() => void act(() => changeHospital(client, a.assignment_id, Number(hospitalId)),
              t("trip.hospital_changed", { name: chosen?.name ?? hospitalId }))}>
            {t("trip.save")}
          </button>
          <button type="button" onClick={() => setEditing(false)} disabled={working}>{t("trip.close")}</button>
        </div>
      )}

      {open && confirming && (
        <div className="trip-confirm" role="dialog" aria-modal="false" aria-labelledby={`trip-c-${a.assignment_id}`}
          onKeyDown={(e) => { if (e.key === "Escape" && !working) closeConfirm(); }}>
          <p id={`trip-c-${a.assignment_id}`}><strong>{t("trip.cancel_title", { plate })}</strong></p>
          <p className="q-muted">{t("trip.cancel_text")}</p>
          <label htmlFor={`trip-r-${a.assignment_id}`}>{t("trip.cancel_reason")}</label>
          <textarea id={`trip-r-${a.assignment_id}`} dir="auto" rows={2} maxLength={500} value={reason}
            onChange={(e) => setReason(e.target.value)} disabled={working} />
          <div className="trip-actions">
            <button type="button" className="trip-cancel" disabled={working}
              onClick={() => void act(() => cancelAssignment(client, a.assignment_id, reason.trim() || null), t("trip.cancelled", { plate }))}>
              {t("trip.cancel_confirm")}
            </button>
            <button type="button" onClick={closeConfirm} disabled={working}>{t("trip.keep")}</button>
          </div>
        </div>
      )}
    </li>
  );
}

export function TripList({ incident }: { incident: IncidentDetailOut }) {
  const { t } = useI18n();
  const { client } = useAuth();
  const assignments = incident.assignments ?? [];
  const vehicles = useQuery({ queryKey: ["vehicles", incident.incident_id],
    queryFn: ({ signal }) => listVehicles(client, { incidentId: incident.incident_id }, signal),
    enabled: assignments.length > 0, staleTime: 5_000 });
  const hospitals = useQuery({ queryKey: ["hospitals"], queryFn: ({ signal }) => listHospitals(client, signal),
    enabled: assignments.some((a) => a.hospital_id != null), staleTime: 60_000 });
  const [message, setMessage] = useState<string | null>(null);
  if (assignments.length === 0) return null;

  const byId = new Map((vehicles.data ?? []).map((v) => [v.vehicle_id, v]));
  const recPlate = new Map((incident.recommendations ?? []).map((r) => [r.vehicle_id, r.plate_number]));
  const hospitalName = (id: number | null | undefined) =>
    id == null ? null : (hospitals.data?.find((h) => h.hospital_id === id)?.name ?? `#${id}`);

  return (
    <section aria-labelledby="trip-heading" className="trips">
      <h4 id="trip-heading">{t("trip.heading")}</h4>
      {message && <p className="dsp-done" role="status">✔ {message}</p>}
      <ul className="trip-list" data-testid="assignments">
        {assignments.map((a) => (
          <TripCard key={a.assignment_id} a={a} onDone={setMessage} hospitalName={hospitalName}
            plate={byId.get(a.vehicle_id)?.plate_number ?? recPlate.get(a.vehicle_id) ?? `#${a.vehicle_id}`}
            vtype={byId.get(a.vehicle_id)?.vehicle_type ?? null} />
        ))}
      </ul>
    </section>
  );
}
