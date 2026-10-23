import { allSettled, fork, scopeBind } from "effector";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CounterpartyOut, ProductOut } from "@shared/models";

import {
  $open,
  $query,
  $results,
  counterpartyHref,
  filterScreens,
  paletteClosed,
  paletteOpened,
  productHref,
  queryChanged,
  searchFx,
  searchable,
  type SearchRequest,
} from "./index.ts";

const product = (id: string, name: string) => ({ id, name }) as ProductOut;
const counterparty = (id: string, name: string) => ({ id, name, phone: null }) as CounterpartyOut;

describe("WEB-12 Ctrl+K palette (06 §1.9, 08 §9)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("searches products and counterparties 250 ms after typing, only what the user may read", async () => {
    const calls: SearchRequest[] = [];
    const s = fork({
      handlers: [
        [
          searchFx,
          (req: SearchRequest) => {
            calls.push(req);
            return {
              products: req.products ? [product("p-1", "Coca-Cola 1.5L")] : [],
              counterparties: req.counterparties ? [counterparty("c-1", "Aliyev Botir")] : [],
            };
          },
        ],
      ],
    });
    await allSettled(paletteOpened, { scope: s, params: { products: true, counterparties: false } });
    expect(s.getState($open)).toBe(true);

    scopeBind(queryChanged, { scope: s })("c");
    scopeBind(queryChanged, { scope: s })("co");
    scopeBind(queryChanged, { scope: s })("coc");
    expect(calls).toEqual([]);
    await vi.advanceTimersByTimeAsync(250);
    expect(calls).toEqual([{ products: true, counterparties: false, query: "coc" }]);
    expect(s.getState($results).products.map((p) => p.name)).toEqual(["Coca-Cola 1.5L"]);
    expect(s.getState($results).counterparties).toEqual([]);

    // One character: no request, results cleared.
    scopeBind(queryChanged, { scope: s })("c");
    await vi.advanceTimersByTimeAsync(250);
    expect(calls).toHaveLength(1);
    expect(s.getState($results).products).toEqual([]);

    await allSettled(paletteClosed, { scope: s });
    expect(s.getState($open)).toBe(false);
    expect(s.getState($query)).toBe("");
  });

  it("no search rights → no request (screens only)", async () => {
    const calls: SearchRequest[] = [];
    const s = fork({
      handlers: [[searchFx, (r: SearchRequest) => (calls.push(r), { products: [], counterparties: [] })]],
    });
    await allSettled(paletteOpened, { scope: s, params: { products: false, counterparties: false } });
    scopeBind(queryChanged, { scope: s })("sut");
    await vi.advanceTimersByTimeAsync(300);
    expect(calls).toEqual([]);
  });
});

describe("palette lib", () => {
  it("screen filter, searchable query, links", () => {
    const screens = [
      { label: "Dashboard", keywords: "ASOSIY" },
      { label: "Qoldiq va ko'chirish", keywords: "OMBOR" },
      { label: "Hisobotlar", keywords: "BOSHQARUV" },
    ];
    expect(filterScreens(screens, "")).toHaveLength(3);
    expect(filterScreens(screens, "ombor").map((s) => s.label)).toEqual(["Qoldiq va ko'chirish"]);
    expect(filterScreens(screens, "HISOB").map((s) => s.label)).toEqual(["Hisobotlar"]);
    expect(searchable(" a ")).toBeNull();
    expect(searchable(" sut ")).toBe("sut");
    expect(productHref("p-1")).toBe("/app/catalog/products/p-1");
    expect(counterpartyHref("c-1")).toBe("/app/debts?counterparty=c-1");
  });
});
