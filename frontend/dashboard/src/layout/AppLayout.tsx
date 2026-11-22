// Signed-in frame: header with the user's name and role, menu for their role, sign-out, service
// banner and the idle warning (NFR-C4).
import { NavLink, Outlet } from "react-router-dom";
import { ServiceStatusBanner, getMe, useHealth, useI18n } from "@amceds/shared";
import { useAuth } from "../auth/AuthProvider";
import { IDLE_WARNING_MIN, useIdleTimer } from "../auth/useIdleTimer";

export function AppLayout() {
  const { t } = useI18n();
  const { user, signOut, client } = useAuth();
  const health = useHealth(client);
  const touchServer = () => void getMe(client).catch(() => undefined); // the server counts requests, not clicks
  const idle = useIdleTimer({ enabled: user !== null, onIdle: () => void signOut("idle"), onKeepAlive: touchServer });

  if (!user) return null;
  const stay = () => {
    idle.stayActive();
    touchServer();
  };

  return (
    <div className="dash">
      <ServiceStatusBanner services={health.down} unreachable={health.unreachable} />
      <header className="dash-header">
        <h1>{t("app.dashboard_title")}</h1>
        <nav className="dash-nav" aria-label="Main">
          {user.role === "dispatcher" && <NavLink to="/queue">{t("nav.queue")}</NavLink>}
          {user.role === "admin" && <NavLink to="/admin">{t("nav.admin")}</NavLink>}
        </nav>
        <span className="dash-user">{t("nav.signed_in_as", { name: user.full_name, role: t(`role.${user.role}`) })}</span>
        <button type="button" onClick={() => void signOut("signed_out")}>{t("nav.logout")}</button>
      </header>
      {idle.warning && (
        <div className="dash-idle" role="alertdialog" aria-live="assertive" aria-label={t("idle.stay")}>
          <p>{t("idle.warning", { minutes: IDLE_WARNING_MIN })}</p>
          <button type="button" onClick={stay}>{t("idle.stay")}</button>
        </div>
      )}
      <main className="dash-main">
        <Outlet />
      </main>
      <footer className="dash-footer">{t("app.simulated")}</footer>
    </div>
  );
}
