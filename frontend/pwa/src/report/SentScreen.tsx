// Shown only after the server answered 201 (saved) or 200 (already saved, TC-04) — never on failure.
import { useEffect, useRef } from "react";
import { useI18n, type ReportAcceptedOut } from "@amceds/shared";

export function SentScreen({ result, alreadySaved, onNewReport }: {
  result: ReportAcceptedOut;
  alreadySaved: boolean;
  onNewReport: () => void;
}) {
  const { t, lang } = useI18n();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);

  const received = new Date(result.received_at);
  const time = Number.isNaN(received.getTime())
    ? result.received_at
    : received.toLocaleString(lang === "ur" ? "ur-PK" : "en-GB", { dateStyle: "medium", timeStyle: "short" });

  return (
    <section className="rf-sent" aria-labelledby="rf-sent-title">
      <h2 id="rf-sent-title" ref={heading} tabIndex={-1}>✔ {t("report.sent_title")}</h2>
      <p>{t("report.sent_reference")}</p>
      <p className="rf-reference" dir="ltr" data-testid="reference-no">{result.reference_no}</p>
      <p>{alreadySaved ? t("report.sent_already") : t("report.sent_text")}</p>
      <p className="rf-muted">{t("report.sent_time", { time })}</p>
      <button type="button" className="rf-primary" onClick={onNewReport}>{t("report.new_report")}</button>
    </section>
  );
}
