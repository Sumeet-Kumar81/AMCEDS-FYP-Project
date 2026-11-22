// Loading / empty / error states (every list and detail screen has all three) and the service banner.
import type { ReactNode } from "react";
import { ApiError } from "../api/errors";
import { useI18n, type MessageKey } from "../i18n/i18n";

export function LoadingState({ text }: { text?: string }) {
  const { t } = useI18n();
  return (
    <div className="am-state am-loading" role="status" aria-live="polite">
      {text ?? t("state.loading")}
    </div>
  );
}

export function EmptyState({ children }: { children?: ReactNode }) {
  const { t } = useI18n();
  return <div className="am-state am-empty">{children ?? t("state.empty")}</div>;
}

const KNOWN_ERROR_TEXT: Record<string, MessageKey> = {
  network_error: "error.network_error",
  timeout: "error.timeout",
  service_unavailable: "error.service_unavailable",
};

/** A user-facing sentence for any error: our own words for known codes, else the server's message. */
export function useErrorText(): (error: unknown) => string {
  const { t } = useI18n();
  return (error) => {
    if (error instanceof ApiError) {
      if (error.notImplemented) {
        const task = (error.details as { task?: string } | null)?.task ?? "";
        return t("error.not_implemented", { task });
      }
      const key = KNOWN_ERROR_TEXT[error.code];
      return key ? t(key) : error.message;
    }
    return t("state.error");
  };
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const text = useErrorText()(error);
  const code = error instanceof ApiError ? error.code : null;
  return (
    <div className="am-state am-error" role="alert">
      <p>{text}</p>
      {code && <p className="am-error-code">({code})</p>}
      {onRetry && (
        <button type="button" onClick={onRetry}>
          {t("state.retry")}
        </button>
      )}
    </div>
  );
}

/**
 * Warns when a service is down (NFR-S5) or the server cannot be reached. Shows nothing when all is well.
 * `services` are names from the health answer (e.g. "database").
 */
export function ServiceStatusBanner({ services, unreachable = false }: { services: string[]; unreachable?: boolean }) {
  const { t } = useI18n();
  if (!unreachable && services.length === 0) return null;
  const names = services.map((s) => (s === "api" || s === "database" ? t(`service.${s}`) : s)).join(", ");
  return (
    <div className="am-service-banner" role="alert">
      <strong>{unreachable ? t("service.unreachable") : t("service.down", { services: names })}</strong>{" "}
      {t("service.down_hint")}
    </div>
  );
}
