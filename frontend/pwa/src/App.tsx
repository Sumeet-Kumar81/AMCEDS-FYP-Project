// Public report page (B1-A3-01 shell, B1-A3-03 form). The 1122 notice is always visible: while the
// form is shown, while sending, on errors and after sending (TC-47, safety rule 10).
import { ApiClient, CallNotice, I18nProvider, LanguageToggle, ServiceStatusBanner, useHealth, useI18n } from "@amceds/shared";
import { ReportPage } from "./report/ReportPage";

function Page({ client, geolocation }: { client: ApiClient; geolocation?: Geolocation }) {
  const { t } = useI18n();
  const health = useHealth(client);
  return (
    <div className="report">
      <ServiceStatusBanner services={health.down} unreachable={health.unreachable} />
      <header className="report-header">
        <h1>{t("app.report_title")}</h1>
        <LanguageToggle />
      </header>
      <main className="report-main">
        <CallNotice />
        <ReportPage client={client} geolocation={geolocation} />
        <p className="report-simulated">{t("app.simulated")}</p>
      </main>
    </div>
  );
}

export function App({ client, geolocation }: { client: ApiClient; geolocation?: Geolocation }) {
  return (
    <I18nProvider initialLang="en">
      <Page client={client} geolocation={geolocation} />
    </I18nProvider>
  );
}
