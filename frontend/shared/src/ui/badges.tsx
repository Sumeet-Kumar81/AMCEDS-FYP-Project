// Shared UI rules, SDS §7.6 (B1-A3-02): the same colours and words everywhere, colour is never the
// only cue, every AI value shows its confidence, every report shows its trust tier.
import type { Severity, TrustTier } from "../api/endpoints";
import { useI18n } from "../i18n/i18n";

/** SRS default for "dispatcher must check" (Appendix C `triage_min_confidence` = 60 %). */
export const DEFAULT_MIN_CONFIDENCE = 0.6;

const SEVERITY_ICON: Record<Severity, string> = { critical: "▲▲", high: "▲", medium: "■", low: "●" };

export function SeverityBadge({ severity }: { severity: Severity | null | undefined }) {
  const { t } = useI18n();
  if (!severity) {
    return <span className="am-badge am-sev-unknown" data-severity="unknown">? {t("severity.unknown")}</span>;
  }
  return (
    <span className={`am-badge am-sev-${severity}`} data-severity={severity}>
      <span aria-hidden="true">{SEVERITY_ICON[severity]} </span>
      {t(`severity.${severity}`)}
    </span>
  );
}

export function TrustBadge({ tier, score }: { tier: TrustTier | null | undefined; score?: number | null }) {
  const { t } = useI18n();
  if (!tier) {
    return (
      <span className="am-badge am-trust-none" data-trust="none">
        {t("trust.label")}: {t("trust.not_scored")}
      </span>
    );
  }
  return (
    <span className={`am-badge am-trust-${tier}`} data-trust={tier}>
      {t("trust.label")}: {t(`trust.${tier}`)}
      {score != null && <> ({score})</>}
    </span>
  );
}

/**
 * Confidence of one AI value (0–1). Below `threshold` it says "Dispatcher must check" (UC-02 4a, TC-08).
 * Pass the incident's own snapshot threshold when the screen has it; the SRS default is 60 %.
 */
export function ConfidenceMeter({
  value,
  threshold = DEFAULT_MIN_CONFIDENCE,
  label,
}: {
  value: number | null | undefined;
  threshold?: number;
  label?: string;
}) {
  const { t } = useI18n();
  const name = label ?? t("confidence.label");
  if (value == null || Number.isNaN(value)) {
    return (
      <span className="am-confidence am-confidence-none">
        {name}: {t("confidence.none")} — <strong>{t("confidence.must_check")}</strong>
      </span>
    );
  }
  const clamped = Math.min(1, Math.max(0, value));
  const percent = Math.round(clamped * 100);
  const low = clamped < threshold;
  return (
    <span className={`am-confidence${low ? " am-confidence-low" : ""}`} data-low={low}>
      <span>
        {name}: {percent}%
      </span>
      <span className="am-confidence-bar" aria-hidden="true">
        <span style={{ width: `${percent}%` }} />
      </span>
      {low && <strong className="am-confidence-warning">{t("confidence.must_check")}</strong>}
    </span>
  );
}

export function AiRecommendationLabel() {
  const { t } = useI18n();
  return <span className="am-ai-label">🤖 {t("ai.recommendation")}</span>;
}

/** Shown whenever `eta_is_approximate` (straight-line estimate, safety rule 7). */
export function ApproximateEtaTag({ approximate }: { approximate: boolean | null | undefined }) {
  const { t } = useI18n();
  if (!approximate) return null;
  return <span className="am-badge am-eta-approx">≈ {t("eta.approximate")}</span>;
}

/** Safety rule 10: always visible on the report page and in the app. */
export function CallNotice() {
  const { t } = useI18n();
  return (
    <p className="am-call-notice" role="note">
      <span aria-hidden="true">☎ </span>
      <strong>{t("notice.call_1122")}</strong>
    </p>
  );
}
