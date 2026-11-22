import { useI18n } from "@amceds/shared";
import type { FieldError } from "./validation";

/** The problem text under one field (our own words, or the server's message). */
export function FieldMessage({ error, id }: { error?: FieldError; id: string }) {
  const { t } = useI18n();
  if (!error) return null;
  return (
    <p className="rf-error" id={id}>
      {error.key ? t(error.key, error.vars) : error.text}
    </p>
  );
}
