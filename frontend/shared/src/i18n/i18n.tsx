// English/Urdu text without a library (SDS §7.6, NFR-P16). Urdu switches the page to right-to-left.
// Sindhi is accepted as free text in reports; the interface itself is English or Urdu.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import en from "./en.json";
import ur from "./ur.json";

export type Lang = "en" | "ur";
export type MessageKey = keyof typeof en;
export type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string;

export const MESSAGES: Record<Lang, Record<MessageKey, string>> = { en, ur };
export const RTL_LANGS: ReadonlySet<Lang> = new Set(["ur"]);

export function dirFor(lang: Lang): "rtl" | "ltr" {
  return RTL_LANGS.has(lang) ? "rtl" : "ltr";
}

/** Looks a key up in `lang`, then English, then shows the key itself (never an empty label). */
export function translate(lang: Lang, key: MessageKey, vars?: Record<string, string | number>): string {
  const text = MESSAGES[lang][key] ?? MESSAGES.en[key] ?? key;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}

interface I18nValue {
  lang: Lang;
  dir: "rtl" | "ltr";
  setLang: (lang: Lang) => void;
  t: Translate;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ initialLang = "en", children }: { initialLang?: Lang; children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(initialLang);
  const t = useCallback<Translate>((key, vars) => translate(lang, key, vars), [lang]);
  const value = useMemo(() => ({ lang, dir: dirFor(lang), setLang, t }), [lang, t]);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dirFor(lang);
  }, [lang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/** Text for the current language. Outside a provider it falls back to English. */
export function useI18n(): I18nValue {
  return (
    useContext(I18nContext) ?? {
      lang: "en",
      dir: "ltr",
      setLang: () => undefined,
      t: (key, vars) => translate("en", key, vars),
    }
  );
}

export function LanguageToggle() {
  const { lang, setLang, t } = useI18n();
  const next: Lang = lang === "en" ? "ur" : "en";
  return (
    <button type="button" className="am-lang-toggle" lang={next} onClick={() => setLang(next)}>
      {t("lang.switch_to")}
    </button>
  );
}
