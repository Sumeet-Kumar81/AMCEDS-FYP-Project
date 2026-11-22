// Incident queue (B1-A3-06; SRS UC-06 1, NFR-S2; SDS §7.2 item 1). The order comes from the server
// (critical, high, unknown, medium, low; longest-waiting first). Refreshed every 5 s while the tab is
// visible; the WebSocket hub (B1-A1-29) replaces the polling later.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  SeverityBadge,
  TrustBadge,
  listIncidents,
  useI18n,
  type IncidentSummaryOut,
} from "@amceds/shared";
import { useAuth } from "../auth/AuthProvider";
import { URGENT_REASONS, clockTime, locationText, minutesAgo, reasonText, statusText, typeText } from "./labels";

export const QUEUE_REFRESH_MS = 5_000;

function IncidentCard({ incident, now, isNewCritical }: { incident: IncidentSummaryOut; now: number; isNewCritical: boolean }) {
  const { t } = useI18n();
  return (
    <li>
      <Link to={`/incidents/${incident.incident_id}`}
        className={`q-card q-sev-${incident.severity ?? "unknown"}${isNewCritical ? " q-new-critical" : ""}`}
        data-testid="incident-card" data-incident={incident.incident_id}>
        <div className="q-row">
          <SeverityBadge severity={incident.severity} />
          <strong className="q-type">{typeText(t, incident.incident_type)}</strong>
          <span className="q-ref" dir="ltr">{incident.reference_no}</span>
          <span className="q-status">{statusText(t, incident.status)}</span>
          <span className="q-time">{minutesAgo(t, incident.received_at, now)}</span>
        </div>
        <div className="q-row q-muted">
          <span className="q-loc" dir="auto">📍 {locationText(t, incident.location)}</span>
          <TrustBadge tier={incident.trust_tier} score={incident.trust_score} />
        </div>
        {incident.status === "new" && <p className="q-reading">⏳ {t("queue.ai_reading")}</p>}
        {(incident.review_reasons ?? []).length > 0 && (
          <ul className="q-flags" aria-label="flags">
            {(incident.review_reasons ?? []).map((code) => (
              <li key={code} className={`q-flag${URGENT_REASONS.has(code) ? " q-flag-urgent" : ""}`} data-reason={code}>
                ⚠ {reasonText(t, code)}
              </li>
            ))}
          </ul>
        )}
      </Link>
    </li>
  );
}

export function QueuePage() {
  const { t, lang } = useI18n();
  const { client } = useAuth();
  const query = useQuery({
    queryKey: ["incidents"],
    queryFn: ({ signal }) => listIncidents(client, {}, signal),
    refetchInterval: QUEUE_REFRESH_MS,
    refetchIntervalInBackground: false,
  });

  // Critical reports that arrived after the first load stay highlighted until opened.
  const seen = useRef<Set<number> | null>(null);
  const [newCritical, setNewCritical] = useState<Set<number>>(new Set());
  useEffect(() => {
    if (!query.data) return;
    if (seen.current === null) {
      seen.current = new Set(query.data.map((i) => i.incident_id));
      return;
    }
    const arrived = query.data.filter((i) => !seen.current!.has(i.incident_id));
    arrived.forEach((i) => seen.current!.add(i.incident_id));
    const critical = arrived.filter((i) => i.severity === "critical").map((i) => i.incident_id);
    if (critical.length) setNewCritical((prev) => new Set([...prev, ...critical]));
  }, [query.data]);

  const open = new Set(query.data?.map((i) => i.incident_id));
  const highlighted = [...newCritical].filter((id) => open.has(id));

  return (
    <section className="dash-page">
      <div className="q-head">
        <h2>{t("queue.title")}</h2>
        {query.data && <span className="q-muted">{t("queue.count", { count: query.data.length })}</span>}
        {query.dataUpdatedAt > 0 && (
          <span className="q-muted" data-testid="updated">{t("queue.updated", { time: clockTime(query.dataUpdatedAt, lang) })}</span>
        )}
      </div>
      {highlighted.length > 0 && (
        <p className="q-new-banner" role="status">🔴 {t("queue.new_critical", { count: highlighted.length })}</p>
      )}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.isPending && !query.isError && <LoadingState />}
      {query.data && query.data.length === 0 && <EmptyState>{t("queue.empty")}</EmptyState>}
      {query.data && query.data.length > 0 && (
        <ul className="q-list">
          {query.data.map((incident) => (
            <IncidentCard key={incident.incident_id} incident={incident} now={query.dataUpdatedAt || Date.now()}
              isNewCritical={newCritical.has(incident.incident_id)} />
          ))}
        </ul>
      )}
    </section>
  );
}
