// Login (UC-11 1, 1a, TC-32). The password is only ever in this form's memory: never in the URL,
// browser storage or logs. Wrong password and locked account each get a clear message.
import { useRef, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError, useErrorText, useI18n, type MessageKey } from "@amceds/shared";
import { DriverNotAllowedError, homeFor, useAuth, type SignOutReason } from "../auth/AuthProvider";
import { IDLE_LOGOUT_MIN } from "../auth/useIdleTimer";

const NOTICE: Record<SignOutReason, MessageKey> = {
  signed_out: "login.notice_signed_out",
  session_ended: "login.notice_session_ended",
  idle: "login.notice_idle",
};

export function LoginPage() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const { user, notice, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);

  if (user && !busy) return <Navigate to={from ?? homeFor(user.role)} replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (inFlight.current) return;
    if (!username.trim() || !password) {
      setError(t("login.err_required"));
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const me = await signIn(username.trim(), password);
      setPassword("");
      navigate(from ?? homeFor(me.role), { replace: true });
    } catch (err) {
      setPassword("");
      if (err instanceof DriverNotAllowedError) setError(t("login.err_driver"));
      else if (err instanceof ApiError && err.code === "invalid_credentials") setError(t("login.err_invalid"));
      else if (err instanceof ApiError && err.code === "account_locked") setError(err.message); // says how long
      else setError(errorText(err));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <form className="login-card" onSubmit={onSubmit} noValidate aria-busy={busy}>
        <h2>{t("login.title")}</h2>
        <p className="login-intro">{t("login.intro")}</p>
        {notice && !error && (
          <p className="login-notice" role="status">{t(NOTICE[notice], { minutes: IDLE_LOGOUT_MIN })}</p>
        )}
        <label htmlFor="login-username">{t("login.username")}</label>
        <input id="login-username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false}
          value={username} onChange={(e) => setUsername(e.target.value)} disabled={busy} autoFocus />
        <label htmlFor="login-password">{t("login.password")}</label>
        <input id="login-password" name="password" type="password" autoComplete="current-password"
          value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy} />
        {error && <p className="login-error" role="alert">{error}</p>}
        <button type="submit" className="login-submit" disabled={busy}>
          {busy ? t("login.signing_in") : t("login.submit")}
        </button>
      </form>
    </main>
  );
}
