// Public report form (B1-A3-03; SRS UC-01 1–5, 2a, 3a, 5b; SDS §7.1; TC-01, TC-03, TC-04, TC-47).
// Text reports go to the real POST /api/v1/reports. A reference number is shown only after the server
// saved the report. One submission id per report: pressing Send again after a lost answer re-sends the
// same id, so the server stores it once; editing the report starts a new submission.
import { useRef, useState, type FormEvent } from "react";
import { ApiClient, ApiError, submitReport, useI18n, type MessageKey, type SubmittedReport } from "@amceds/shared";
import { FieldMessage } from "./FieldMessage";
import { LocationField } from "./LocationField";
import { SentScreen } from "./SentScreen";
import { useGeolocation } from "./useGeolocation";
import {
  EMPTY_DRAFT,
  LIMITS,
  newRequestId,
  sameDraft,
  serverFieldErrors,
  toReportIn,
  validate,
  type Field,
  type FieldErrors,
  type ReportDraft,
} from "./validation";

interface FormProblem {
  key: MessageKey;
  vars?: Record<string, string | number>;
}

const FIELD_IDS: Record<Field, string> = {
  description: "rf-description",
  addressText: "rf-address",
  name: "rf-name",
  phone: "rf-phone",
  location: "rf-address",
};

function problemFor(error: unknown): FormProblem {
  if (error instanceof ApiError) {
    if (error.status === 422) return { key: "report.err_fix" };
    if (error.status === 503) return { key: "report.err_not_saved" };
    if (error.status === 429) return { key: "report.err_too_many" };
    if (error.noConnection) return { key: "report.err_not_sent" };
    return { key: "report.err_other", vars: { code: error.code } };
  }
  return { key: "report.err_other", vars: { code: "unknown" } };
}

export function ReportPage({ client, geolocation }: { client: ApiClient; geolocation?: Geolocation }) {
  const { t } = useI18n();
  const geo = useGeolocation(geolocation ?? globalThis.navigator?.geolocation);
  const [fields, setFields] = useState({ ...EMPTY_DRAFT });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [problem, setProblem] = useState<FormProblem | null>(null);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<SubmittedReport | null>(null);
  const inFlight = useRef(false);
  const pending = useRef<{ id: string; draft: ReportDraft } | null>(null);

  const draft: ReportDraft = { ...fields, gps: geo.fix };
  const update = (name: keyof typeof EMPTY_DRAFT) => (value: string) => {
    setFields((f) => ({ ...f, [name]: value }));
    setErrors((e) => ({ ...e, [name]: undefined }));
  };

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (inFlight.current) return; // never two requests for one press (double tap)
    const found = validate(draft);
    setErrors(found);
    const first = (Object.keys(found) as Field[])[0];
    if (first) {
      setProblem({ key: "report.err_fix" });
      document.getElementById(FIELD_IDS[first])?.focus();
      return;
    }

    if (!pending.current || !sameDraft(pending.current.draft, draft)) {
      pending.current = { id: newRequestId(), draft };
    }
    inFlight.current = true;
    setSending(true);
    setProblem(null);
    try {
      const result = await submitReport(client, toReportIn(draft, pending.current.id));
      pending.current = null;
      setSent(result);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) setErrors(serverFieldErrors(error.validationIssues));
      setProblem(problemFor(error));
    } finally {
      inFlight.current = false;
      setSending(false);
    }
  }

  function startNewReport() {
    setFields({ ...EMPTY_DRAFT });
    setErrors({});
    setProblem(null);
    setSent(null);
    geo.clear();
    pending.current = null;
  }

  if (sent) return <SentScreen result={sent.report} alreadySaved={sent.alreadySaved} onNewReport={startNewReport} />;

  const length = fields.description.trim().length;
  const described = (field: Field, hint?: string) =>
    [hint, errors[field] ? `${FIELD_IDS[field]}-error` : undefined].filter(Boolean).join(" ") || undefined;

  return (
    <form className="rf" onSubmit={onSubmit} noValidate aria-busy={sending}>
      <p className="rf-intro">{t("report.intro")}</p>

      <div className="rf-group">
        <label htmlFor="rf-description">
          {t("report.description_label")} <span className="rf-tag rf-required">({t("report.required")})</span>
        </label>
        <p className="rf-hint" id="rf-description-hint">{t("report.description_hint")}</p>
        <textarea id="rf-description" dir="auto" rows={5} value={fields.description} disabled={sending}
          onChange={(e) => update("description")(e.target.value)} aria-invalid={errors.description ? true : undefined}
          aria-describedby={described("description", "rf-description-hint")} />
        <p className={`rf-counter${length > LIMITS.description ? " rf-over" : ""}`} aria-live="polite">
          {t("report.chars", { count: length, max: LIMITS.description })}
        </p>
        <FieldMessage error={errors.description} id="rf-description-error" />
      </div>

      <LocationField status={geo.status} fix={geo.fix} onLocate={geo.request} onClear={geo.clear}
        addressText={fields.addressText} onAddressChange={update("addressText")} addressError={errors.addressText}
        locationError={errors.location} disabled={sending} />

      <fieldset className="rf-group">
        <legend>
          {t("report.details_heading")} <span className="rf-tag">({t("report.optional")})</span>
        </legend>
        <label htmlFor="rf-name">{t("report.name_label")}</label>
        <input id="rf-name" type="text" dir="auto" autoComplete="name" value={fields.name} disabled={sending}
          onChange={(e) => update("name")(e.target.value)} aria-invalid={errors.name ? true : undefined}
          aria-describedby={described("name")} />
        <FieldMessage error={errors.name} id="rf-name-error" />
        <label htmlFor="rf-phone">{t("report.phone_label")}</label>
        <p className="rf-hint" id="rf-phone-hint">{t("report.phone_hint")}</p>
        <input id="rf-phone" type="tel" inputMode="tel" dir="ltr" autoComplete="tel" value={fields.phone}
          disabled={sending} onChange={(e) => update("phone")(e.target.value)}
          aria-invalid={errors.phone ? true : undefined} aria-describedby={described("phone", "rf-phone-hint")} />
        <FieldMessage error={errors.phone} id="rf-phone-error" />
      </fieldset>

      <div className="rf-group rf-voice">
        <button type="button" disabled aria-describedby="rf-voice-note">🎤 {t("report.voice")}</button>
        <p className="rf-hint" id="rf-voice-note">{t("report.voice_note")}</p>
      </div>

      {problem && <div className="rf-problem" role="alert">{t(problem.key, problem.vars)}</div>}

      <button type="submit" className="rf-primary rf-send" disabled={sending}>
        {sending ? t("report.sending") : t("report.send")}
      </button>
      <p className="rf-muted">{t("report.privacy")}</p>
    </form>
  );
}
