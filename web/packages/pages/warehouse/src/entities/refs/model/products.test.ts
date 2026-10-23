/** WEB-10: product cards — at most 6 requests at once, an id already in flight is not fetched again. */
import { allSettled, fork, scopeBind } from "effector";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type * as ApiModule from "@shared/api";

import type { ProductOut } from "@shared/models";

const { getProduct } = vi.hoisted(() => ({ getProduct: vi.fn<(id: string) => Promise<ProductOut>>() }));

vi.mock("@shared/api", async (importOriginal) => {
  const actual = await importOriginal<typeof ApiModule>();
  return { ...actual, api: { ...actual.api, pricing: { ...actual.api.pricing, getProduct } } };
});

const { $inFlight, $products, PRODUCT_FETCH_CONCURRENCY, productsRequested } = await import("./index.ts");

const card = (id: string) => ({ id, name: id }) as ProductOut;

describe("product cache (WEB-10)", () => {
  let waiting: (() => void)[] = [];
  let running = 0;
  let peak = 0;

  beforeEach(() => {
    waiting = [];
    running = 0;
    peak = 0;
    getProduct.mockReset().mockImplementation(
      (id) =>
        new Promise<ProductOut>((resolve) => {
          running += 1;
          peak = Math.max(peak, running);
          waiting.push(() => {
            running -= 1;
            resolve(card(id));
          });
        }),
    );
  });

  const drain = async () => {
    while (waiting.length > 0) {
      for (const done of waiting.splice(0)) done();
      await new Promise((r) => setTimeout(r, 0));
    }
  };

  it("overlapping requests fetch each id once", async () => {
    const s = fork();
    const request = scopeBind(productsRequested, { scope: s });
    request(["p-1", "p-2"]);
    request(["p-2", "p-3", "p-1"]);
    expect([...s.getState($inFlight)].sort()).toEqual(["p-1", "p-2", "p-3"]);
    await drain();
    await allSettled(s);
    expect(getProduct.mock.calls.map(([id]) => id).sort()).toEqual(["p-1", "p-2", "p-3"]);
    expect(Object.keys(s.getState($products)).sort()).toEqual(["p-1", "p-2", "p-3"]);
    expect(s.getState($inFlight).size).toBe(0);
  });

  it(`no more than ${PRODUCT_FETCH_CONCURRENCY} cards are read at once`, async () => {
    const s = fork();
    const ids = Array.from({ length: 20 }, (_, i) => `p-${i}`);
    scopeBind(productsRequested, { scope: s })(ids);
    await new Promise((r) => setTimeout(r, 0));
    expect(running).toBe(PRODUCT_FETCH_CONCURRENCY);
    await drain();
    await allSettled(s);
    expect(peak).toBe(PRODUCT_FETCH_CONCURRENCY);
    expect(getProduct).toHaveBeenCalledTimes(20);
    expect(Object.keys(s.getState($products))).toHaveLength(20);
  });
});
