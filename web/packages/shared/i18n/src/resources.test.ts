import { describe, expect, it } from "vitest";

import { initI18n, translateMessageKey } from "./index.ts";
import { resources } from "./resources.ts";

type Tree = { [key: string]: string | Tree };

function keys(tree: Tree, prefix = ""): string[] {
  return Object.entries(tree).flatMap(([k, v]) =>
    typeof v === "string" ? [`${prefix}${k}`] : keys(v, `${prefix}${k}.`),
  );
}

function leaves(tree: Tree, prefix = ""): [string, string][] {
  return Object.entries(tree).flatMap(([k, v]): [string, string][] =>
    typeof v === "string" ? [[`${prefix}${k}`, v]] : leaves(v, `${prefix}${k}.`),
  );
}

describe("i18n resources — 08 §11", () => {
  it.each(Object.keys(resources.uz))("ru/%s.json has exactly the uz keys", (ns) => {
    const uz = keys(resources.uz[ns as keyof typeof resources.uz]).sort();
    const ru = keys(resources.ru[ns as keyof typeof resources.ru]).sort();
    expect(ru).toEqual(uz);
  });

  it.each(["uz", "ru"] as const)("%s has no empty or whitespace-only values", (lang) => {
    const empty = Object.entries(resources[lang]).flatMap(([ns, tree]) =>
      leaves(tree, `${ns}:`)
        .filter(([, value]) => value.trim().length === 0)
        .map(([key]) => key),
    );
    expect(empty).toEqual([]);
  });

  it("translates server message_key and falls back to internal_error", async () => {
    const i18n = initI18n("uz");
    expect(translateMessageKey("errors.invalid_credentials")).toBe("Telefon yoki parol noto'g'ri");
    expect(translateMessageKey("errors.something_unknown")).toBe("Xatolik yuz berdi. Qayta urinib ko'ring");
    await i18n.changeLanguage("ru");
    expect(translateMessageKey("errors.invalid_credentials")).toBe("Неверный телефон или пароль");
  });
});
