// Admin start page. Its content is built in B1-A1-31; until then it says so plainly (no fake admin data).
import { useI18n } from "@amceds/shared";

export function AdminPage() {
  const { t } = useI18n();
  return (
    <section className="dash-page">
      <h2>{t("admin.title")}</h2>
      <p className="dash-not-built">{t("admin.not_built")}</p>
    </section>
  );
}
