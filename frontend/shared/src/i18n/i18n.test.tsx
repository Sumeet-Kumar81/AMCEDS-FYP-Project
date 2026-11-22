// English/Urdu text and RTL (SDS §7.6, NFR-P16).
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import en from "./en.json";
import { I18nProvider, LanguageToggle, MESSAGES, dirFor, translate, useI18n } from "./i18n";
import ur from "./ur.json";

function Probe() {
  const { t, dir, lang } = useI18n();
  return <p data-testid="probe" data-dir={dir} data-lang={lang}>{t("notice.call_1122")}</p>;
}

describe("i18n", () => {
  it("Urdu has every English key and no empty text", () => {
    expect(Object.keys(ur).sort()).toEqual(Object.keys(en).sort());
    for (const lang of ["en", "ur"] as const) {
      for (const [key, text] of Object.entries(MESSAGES[lang])) expect(text.trim(), `${lang}:${key}`).not.toBe("");
    }
  });

  it("Urdu is right-to-left, English left-to-right", () => {
    expect(dirFor("ur")).toBe("rtl");
    expect(dirFor("en")).toBe("ltr");
  });

  it("fills in values and leaves unknown placeholders visible", () => {
    expect(translate("en", "error.not_implemented", { task: "B1-A1-20" })).toBe("This part is not built yet (B1-A1-20).");
    expect(translate("en", "service.down")).toContain("{services}");
  });

  it("the toggle switches the text and the page direction", async () => {
    render(
      <I18nProvider>
        <Probe />
        <LanguageToggle />
      </I18nProvider>,
    );
    expect(screen.getByTestId("probe")).toHaveTextContent("If life is in danger, also call 1122.");
    expect(document.documentElement).toHaveAttribute("dir", "ltr");

    await userEvent.click(screen.getByRole("button", { name: "اردو" }));
    expect(screen.getByTestId("probe")).toHaveTextContent("اگر جان کو خطرہ ہو تو 1122 پر بھی کال کریں۔");
    expect(screen.getByTestId("probe")).toHaveAttribute("data-dir", "rtl");
    expect(document.documentElement).toHaveAttribute("dir", "rtl");
    expect(document.documentElement).toHaveAttribute("lang", "ur");

    await userEvent.click(screen.getByRole("button", { name: "English" }));
    expect(document.documentElement).toHaveAttribute("dir", "ltr");
  });

  it("works in English without a provider", () => {
    render(<Probe />);
    expect(screen.getByTestId("probe")).toHaveAttribute("data-lang", "en");
  });
});
