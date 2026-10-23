import { describe, expect, it } from "vitest";

// The backend permission catalog (15 §2.1) is code; every code it can return must be translated.
import permissionsPy from "../../../../../backend/app/modules/access/domain/permissions.py?raw";

import { resources } from "./resources.ts";

type Tree = { [key: string]: string | Tree };

function lookup(tree: Tree, path: string): string | undefined {
  let node: string | Tree | undefined = tree;
  for (const part of path.split(".")) {
    if (node === undefined || typeof node === "string") return undefined;
    node = node[part];
  }
  return typeof node === "string" ? node : undefined;
}

const entries = [...permissionsPy.matchAll(/_P\("([a-z0-9_.]+)",\s*"([^"]+)"/g)].map((m) => ({
  code: m[1] ?? "",
  modules: (m[2] ?? "").split(/[,/]/).map((s) => s.trim()),
}));

describe("BO-11 permission catalog i18n (WEB-06)", () => {
  it("parses the backend catalog", () => {
    expect(entries.length).toBeGreaterThan(60);
    expect(entries.map((e) => e.code)).toContain("sales.create");
  });

  it.each(["uz", "ru"] as const)("%s has settings:permissions.<code> for every backend code", (lang) => {
    const tree = resources[lang].settings as unknown as Tree;
    expect(entries.filter((e) => !lookup(tree, `permissions.${e.code}`)).map((e) => e.code)).toEqual([]);
  });

  it.each(["uz", "ru"] as const)("%s has settings:modules.<Mxx> for every module", (lang) => {
    const modules = (resources[lang].settings as unknown as { modules: Record<string, string> }).modules;
    const codes = [...new Set(entries.flatMap((e) => e.modules))];
    expect(codes.filter((m) => !modules[m])).toEqual([]);
  });
});
