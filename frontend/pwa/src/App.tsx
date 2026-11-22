// Public report page shell (B1-A3-01). The form itself comes in F2 (B1-A3-03).
// The 1122 notice is always visible, even while loading or when the server is down (TC-47).
import { ApiClient, CallNotice, I18nProvider, LanguageToggle, ServiceStatusBanner, useHealth, useI18n } from "@amceds/shared";

function Page({ client }: { client: ApiClient }) {
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
        <p>{t("placeholder.report")}</p>
        <p className="report-simulated">{t("app.simulated")}</p>
      </main>
    </div>
  );
}

export function App({ client }: { client: ApiClient }) {
  return (
    <I18nProvider initialLang="en">
      <Page client={client} />
    </I18nProvider>
  );
}
