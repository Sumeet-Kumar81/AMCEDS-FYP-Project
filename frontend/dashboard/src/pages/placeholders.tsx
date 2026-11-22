// Start pages per role. Their content is built in later groups; until then they say so plainly
// (no made-up incidents, no fake admin data).
import { useI18n } from "@amceds/shared";

export function QueuePage() {
  const { t } = useI18n();
  return (
    <section className="dash-page">
      <h2>{t("queue.title")}</h2>
      <p className="dash-not-built">{t("queue.not_built")}</p>
    </section>
  );
}

export function AdminPage() {
  const { t } = useI18n();
  return (
    <section className="dash-page">
      <h2>{t("admin.title")}</h2>
      <p className="dash-not-built">{t("admin.not_built")}</p>
    </section>
  );
}
