// Words for incident values (type, status, review reasons, location, times). Unknown codes are shown
// as they are, so a new backend value is never hidden.
import type { LocationOut, MessageKey, Translate } from "@amceds/shared";

const has = (t: Translate, key: string): key is MessageKey => t(key as MessageKey) !== key;

export function typeText(t: Translate, type: string | null | undefined): string {
  return type ? (has(t, `type.${type}`) ? t(`type.${type}` as MessageKey) : type) : t("type.unknown");
}

export function statusText(t: Translate, status: string): string {
  return has(t, `status.${status}`) ? t(`status.${status}` as MessageKey) : status;
}

export function channelText(t: Translate, channel: string): string {
  return has(t, `channel.${channel}`) ? t(`channel.${channel}` as MessageKey) : channel;
}

export function vehicleText(t: Translate, vtype: string): string {
  return has(t, `vehicle.${vtype}`) ? t(`vehicle.${vtype}` as MessageKey) : vtype;
}

export function reasonText(t: Translate, code: string): string {
  return has(t, `reason.${code}`) ? t(`reason.${code}` as MessageKey) : code;
}

/** Reasons that need the dispatcher's eye first get the warning colour. */
export const URGENT_REASONS: ReadonlySet<string> = new Set(["ai_failed", "low_trust_urgent", "vehicle_shortage", "missing_info",
  "vehicle_declined", "vehicle_cancelled"]);

export function locationText(t: Translate, loc: LocationOut): string {
  const parts: string[] = [];
  if (loc.text) parts.push(loc.text);
  if (loc.lat != null && loc.lon != null) parts.push(t("loc.gps", { lat: loc.lat.toFixed(4), lon: loc.lon.toFixed(4) }));
  return parts.length ? parts.join(" · ") : t("loc.unknown");
}

export function minutesAgo(t: Translate, iso: string, now: number): string {
  const minutes = Math.floor((now - new Date(iso).getTime()) / 60_000);
  return minutes < 1 ? t("queue.just_now") : t("queue.minutes_ago", { minutes });
}

export function clockTime(iso: string | number, lang: string): string {
  return new Date(iso).toLocaleTimeString(lang === "ur" ? "ur-PK" : "en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function dateTime(iso: string, lang: string): string {
  return new Date(iso).toLocaleString(lang === "ur" ? "ur-PK" : "en-GB", { dateStyle: "medium", timeStyle: "medium" });
}
