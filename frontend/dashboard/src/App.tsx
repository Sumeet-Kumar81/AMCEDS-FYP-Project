// Dispatcher dashboard shell (B1-A3-01). Sign-in comes in F3 (B1-A3-04), the incident screens in F4.
import { ApiClient, I18nProvider, LoadingState, ServiceStatusBanner, useHealth, useI18n } from "@amceds/shared";

function Shell({ client }: { client: ApiClient }) {
  const { t } = useI18n();
  const health = useHealth(client);
  return (
    <div className="dash">
      <ServiceStatusBanner services={health.down} unreachable={health.unreachable} />
      <header className="dash-header">
        <h1>{t("app.dashboard_title")}</h1>
        <span className="dash-simulated">{t("app.simulated")}</span>
      </header>
      <main className="dash-main">
        {!health.checked ? (
          <LoadingState />
        ) : (
          <>
            {health.health && health.down.length === 0 && <p className="dash-ok">✔ {t("status.connected")}</p>}
            <p>{t("placeholder.dashboard")}</p>
          </>
        )}
      </main>
    </div>
  );
}

export function App({ client }: { client: ApiClient }) {
  return (
    <I18nProvider initialLang="en">
      <Shell client={client} />
    </I18nProvider>
  );
}
