// Route guards: signed-out users go to the login page (and come back afterwards); a wrong role sees
// "Not allowed". The server checks the role on every call too (401/403); this only keeps the screens tidy.
import type { ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useI18n, type UserRole } from "@amceds/shared";
import { homeFor, useAuth } from "./AuthProvider";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

export function RequireRole({ roles, children }: { roles: UserRole[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user) return null; // RequireAuth handles this case
  if (!roles.includes(user.role)) return <NotAllowed />;
  return <>{children}</>;
}

export function NotAllowed() {
  const { t } = useI18n();
  const { user } = useAuth();
  return (
    <section className="dash-page" role="alert">
      <h2>{t("page.not_allowed_title")}</h2>
      <p>{t("page.not_allowed")}</p>
      {user && <Link to={homeFor(user.role)}>{t("page.go_home")}</Link>}
    </section>
  );
}

export function HomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={user ? homeFor(user.role) : "/login"} replace />;
}
