import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { resources } from "./resources.ts";

/** Every `errors.*` / `validation.*` message_key the backend can emit must have a uz and ru text (08 §11). */
const BACKEND_APP = fileURLToPath(new URL("../../../../../backend/app", import.meta.url));
const KEY_RE = /["']((?:errors|validation)\.[a-z0-9_]+)["']/g;

function pythonFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return pythonFiles(path);
    return entry.name.endsWith(".py") ? [path] : [];
  });
}

function backendKeys(): Map<string, string> {
  if (!existsSync(BACKEND_APP)) {
    throw new Error(`backend sources not found at ${BACKEND_APP} — this test needs the monorepo checkout`);
  }
  const found = new Map<string, string>();
  for (const file of pythonFiles(BACKEND_APP)) {
    for (const match of readFileSync(file, "utf8").matchAll(KEY_RE)) {
      const key = match[1];
      if (key !== undefined && !found.has(key)) found.set(key, relative(BACKEND_APP, file));
    }
  }
  return found;
}

type Tree = { [key: string]: string | Tree };

function lookup(tree: Tree, key: string): unknown {
  return key.split(".").reduce<unknown>((node, part) => (node as Tree | undefined)?.[part], tree);
}

describe("backend message_key coverage — 08 §11", () => {
  const keys = backendKeys();

  it("scans a non-trivial set of backend keys", () => {
    expect(keys.size).toBeGreaterThan(50);
  });

  it.each(["uz", "ru"] as const)(
    "%s/common.json translates every backend errors./validation. key",
    (lang) => {
      const common = resources[lang].common as Tree;
      const missing = [...keys]
        .filter(([key]) => typeof lookup(common, key) !== "string")
        .map(([key, file]) => `${key} (${file})`);
      expect(missing).toEqual([]);
    },
  );
});
