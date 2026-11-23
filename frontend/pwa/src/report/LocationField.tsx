// "Where?" part of the report form: browser GPS and/or a typed place or landmark.
import { useI18n } from "@amceds/shared";
import type { GeoStatus } from "./useGeolocation";
import type { FieldError, GpsFix } from "./validation";
import { FieldMessage } from "./FieldMessage";

interface Props {
  status: GeoStatus;
  fix: GpsFix | null;
  onLocate: () => void;
  onClear: () => void;
  addressText: string;
  onAddressChange: (value: string) => void;
  addressError?: FieldError;
  locationError?: FieldError;
  disabled: boolean;
}

export function LocationField(props: Props) {
  const { t } = useI18n();
  const { status, fix } = props;
  const problem =
    status === "denied" ? "report.location_denied"
      : status === "unavailable" ? "report.location_unavailable"
        : status === "unsupported" ? "report.location_unsupported"
          : null;

  return (
    <fieldset className="rf-group">
      <legend>{t("report.location_heading")}</legend>

      <div className="rf-gps">
        {fix ? (
          <>
            <p className="rf-gps-ok" role="status">
              📍 {fix.accuracy != null
                ? t("report.location_ok", { meters: fix.accuracy })
                : t("report.location_ok_no_accuracy")}
            </p>
            <button type="button" onClick={props.onClear} disabled={props.disabled}>
              {t("report.location_remove")}
            </button>
          </>
        ) : (
          <button type="button" className="rf-locate" onClick={props.onLocate}
            disabled={props.disabled || status === "locating"}>
            📍 {status === "locating" ? t("report.locating") : t("report.use_location")}
          </button>
        )}
        {problem && <p className="rf-warning" role="alert">{t(problem)}</p>}
        <FieldMessage error={props.locationError} id="rf-location-error" />
      </div>

      <label htmlFor="rf-address">
        {t("report.address_label")} <span className="rf-tag rf-required">({t("report.required")})</span>
      </label>
      <input id="rf-address" type="text" dir="auto" autoComplete="street-address"
        value={props.addressText} onChange={(e) => props.onAddressChange(e.target.value)} disabled={props.disabled}
        placeholder={t("report.address_hint")} aria-invalid={props.addressError ? true : undefined}
        aria-describedby={props.addressError ? "rf-address-error" : undefined} />
      <FieldMessage error={props.addressError} id="rf-address-error" />

    </fieldset>
  );
}
