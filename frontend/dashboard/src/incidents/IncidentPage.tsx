// Incident review, read-only part (B1-A3-07; SRS UC-06 1–2, UC-02 1a/2a/4a, NFR-S2; SDS §7.2 items 2–6).
// Shows the report exactly as sent, what the AI understood with the confidence of every value, the
// trust reasons, why the dispatcher should look, and the recommended vehicles. Everything from the AI is
// labelled as a recommendation. Dispatch approval is not built (B1-A1-25), so no vehicle can be sent here.
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AiRecommendationLabel,
  ApiError,
  ConfidenceMeter,
  ErrorState,
  LoadingState,
  SeverityBadge,
  TrustBadge,
  getIncident,
  useI18n,
  type IncidentDetailOut,
  type Translate,
} from "@amceds/shared";
import { useAuth } from "../auth/AuthProvider";
import { DispatchPanel } from "../dispatch/DispatchPanel";
import { TripList } from "../dispatch/TripList";
import { URGENT_REASONS, channelText, dateTime, locationText, reasonText, statusText, typeText, vehicleText } from "./labels";

export const DETAIL_REFRESH_MS = 5_000;

interface Triage {
  incident_type?: string | null;
  type_confidence?: number | null;
  severity?: string | null;
  severity_confidence?: number | null;
  victims_estimate?: number | null;
  victims_confidence?: number | null;
  language?: string | null;
  language_confidence?: number | null;
  missing_fields?: string[];
}

interface Allocation {
  needed?: Record<string, number>;
  shortage?: Record<string, number> | null;
  victims_unknown_check?: boolean;
}

function countsText(t: Translate, counts: Record<string, number>): string {
  return Object.entries(counts).filter(([, n]) => n > 0).map(([type, n]) => `${n} × ${vehicleText(t, type)}`).join(", ");
}

function AiSection({ incident }: { incident: IncidentDetailOut }) {
  const { t } = useI18n();
  const triage = (incident.ai_details as { triage?: Triage } | null)?.triage;
  const failed = (incident.review_reasons ?? []).includes("ai_failed");
  const unknown = t("inc.unknown_value");
  const rows: [string, string, number | null | undefined][] = triage
    ? [
        [t("inc.field_type"), typeText(t, triage.incident_type ?? incident.incident_type), triage.type_confidence],
        [t("inc.field_severity"), triage.severity ?? incident.severity ?? unknown, triage.severity_confidence],
        [t("inc.field_victims"), String(triage.victims_estimate ?? incident.victims_estimate ?? unknown), triage.victims_confidence],
        [t("inc.field_language"), triage.language ?? incident.language ?? unknown, triage.language_confidence],
      ]
    : [];
  return (
    <section className="inc-box" aria-labelledby="inc-ai">
      <h3 id="inc-ai">{t("inc.ai_heading")}</h3>
      <AiRecommendationLabel />
      {failed && <p className="inc-alert" role="alert">{t("inc.ai_failed")}</p>}
      {!triage && !failed && incident.status === "new" && <p className="q-reading">⏳ {t("queue.ai_reading")}</p>}
      {triage && (
        <>
          <table className="inc-ai-table">
            <tbody>
              {rows.map(([name, value, confidence]) => (
                <tr key={name} data-testid="ai-row">
                  <th scope="row">{name}</th>
                  <td>{name === t("inc.field_severity") ? <SeverityBadge severity={incident.severity} /> : value}</td>
                  <td><ConfidenceMeter value={confidence} label={name} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p><ConfidenceMeter value={incident.confidence} label={t("inc.field_overall")} /></p>
          {triage.missing_fields && triage.missing_fields.length > 0 && (
            <p className="inc-warn">{t("inc.missing", { fields: triage.missing_fields.join(", ") })}</p>
          )}
        </>
      )}
    </section>
  );
}

function VehiclesSection({ incident }: { incident: IncidentDetailOut }) {
  const { t } = useI18n();
  const alloc = incident.allocation_summary as Allocation | null;
  return (
    <section className="inc-box" aria-labelledby="inc-vehicles">
      <h3 id="inc-vehicles">{t("inc.vehicles_heading")}</h3>
      <AiRecommendationLabel />
      {alloc?.needed && countsText(t, alloc.needed) && <p>{t("inc.needed", { list: countsText(t, alloc.needed) })}</p>}
      {alloc?.shortage && countsText(t, alloc.shortage) && (
        <p className="inc-alert" role="alert">{t("inc.shortage", { list: countsText(t, alloc.shortage) })}</p>
      )}
      {alloc?.victims_unknown_check && <p className="inc-warn">{t("inc.victims_check")}</p>}
      {(incident.recommendations ?? []).length === 0 && <p className="q-muted">{t("inc.no_recs")}</p>}
      <DispatchPanel incident={incident} />
      <TripList incident={incident} />
    </section>
  );
}

export function IncidentPage() {
  const { t, lang } = useI18n();
  const { client } = useAuth();
  const id = Number(useParams().incidentId);
  const valid = Number.isInteger(id) && id > 0;
  const query = useQuery({
    queryKey: ["incident", id],
    queryFn: ({ signal }) => getIncident(client, id, signal),
    enabled: valid,
    refetchInterval: (q) => (q.state.error instanceof ApiError && q.state.error.status === 404 ? false : DETAIL_REFRESH_MS),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 1,
  });
  const back = <Link to="/queue" className="inc-back">{t("inc.back")}</Link>;

  if (!valid || (query.error instanceof ApiError && query.error.status === 404)) {
    return <section className="dash-page">{back}<p role="alert">{t("inc.not_found")}</p></section>;
  }
  if (query.isPending) return <section className="dash-page">{back}<LoadingState /></section>;
  if (!query.data) return <section className="dash-page">{back}<ErrorState error={query.error} onRetry={() => void query.refetch()} /></section>;

  const incident = query.data;
  return (
    <section className="dash-page inc">
      {back}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      <header className="inc-head">
        <h2 dir="ltr">{incident.reference_no}</h2>
        <SeverityBadge severity={incident.severity} />
        <strong>{typeText(t, incident.incident_type)}</strong>
        <span className="q-status">{statusText(t, incident.status)}</span>
        <TrustBadge tier={incident.trust_tier} score={incident.trust_score} />
      </header>

      <div className="inc-grid">
        <section className="inc-box" aria-labelledby="inc-report">
          <h3 id="inc-report">{t("inc.report_heading")}</h3>
          <blockquote className="inc-text" dir="auto" data-testid="original-text">
            {incident.original_text ?? t("inc.no_text")}
          </blockquote>
          {incident.reporter_name && <p>{t("inc.reporter", { name: incident.reporter_name })}</p>}
          <p className="q-muted">{t("inc.received", { time: dateTime(incident.received_at, lang), channel: channelText(t, incident.channel) })}</p>
          <h4>{t("inc.location_heading")}</h4>
          <p dir="auto">📍 {locationText(t, incident.location)}</p>
        </section>

        <AiSection incident={incident} />

        <section className="inc-box" aria-labelledby="inc-trust">
          <h3 id="inc-trust">{t("inc.trust_heading")}</h3>
          <TrustBadge tier={incident.trust_tier} score={incident.trust_score} />
          <p className="q-muted">{t("inc.trust_start")}</p>
          {(incident.trust_signals ?? []).length === 0 ? (
            <p className="q-muted">{t("inc.trust_none")}</p>
          ) : (
            <ul className="inc-signals">
              {(incident.trust_signals ?? []).map((s) => (
                <li key={s.code} data-testid="trust-signal">
                  <strong dir="ltr">{s.points > 0 ? `+${s.points}` : s.points}</strong> {s.detail ?? s.code}
                </li>
              ))}
            </ul>
          )}
        </section>

        {(incident.review_reasons ?? []).length > 0 && (
          <section className="inc-box" aria-labelledby="inc-reasons">
            <h3 id="inc-reasons">{t("inc.reasons_heading")}</h3>
            <ul className="q-flags">
              {(incident.review_reasons ?? []).map((code) => (
                <li key={code} className={`q-flag${URGENT_REASONS.has(code) ? " q-flag-urgent" : ""}`}>⚠ {reasonText(t, code)}</li>
              ))}
            </ul>
          </section>
        )}

        <VehiclesSection incident={incident} />
      </div>
    </section>
  );
}
