/* eslint-disable @typescript-eslint/require-await, @typescript-eslint/prefer-promise-reject-errors -- fake axios rejects with ApiError-shaped objects */
/**
 * X-Actor-User-Id binding (device-auth.md §4): header on /api/v1 calls except sync/auth; 403
 * actor_not_verified → online PIN re-prompt → the SAME request (same Idempotency-Key) retried once.
 */
import { describe, expect, it } from "vitest";

import { ACTOR_HEADER, actorHeaderApplies, installActorBinding, type HttpLike } from "./actor.ts";

type Cfg = {
  url?: string;
  headers: Map<string, string> & { set(n: string, v: string): unknown };
  method?: string;
  _actorRetried?: boolean;
};

function fakeHttp(answers: ("ok" | "not_verified" | "required" | "forbidden")[]) {
  const req: ((c: Cfg) => Cfg)[] = [];
  const res: ((e: unknown) => unknown)[] = [];
  const sent: { url?: string; actor?: string; key?: string }[] = [];
  const http = {
    interceptors: {
      request: { use: (f: (c: Cfg) => Cfg) => req.push(f) - 1, eject: () => undefined },
      response: { use: (_: unknown, r: (e: unknown) => unknown) => res.push(r) - 1, eject: () => undefined },
    },
    async request(config: Cfg): Promise<unknown> {
      for (const f of req) f(config);
      sent.push({
        url: config.url,
        actor: config.headers.get(ACTOR_HEADER),
        key: config.headers.get("Idempotency-Key"),
      });
      const answer = answers.shift() ?? "ok";
      if (answer === "ok") return { data: "done" };
      const error = {
        status: 403,
        code: "PERMISSION_DENIED",
        params: {
          reason:
            answer === "not_verified"
              ? "actor_not_verified"
              : answer === "required"
                ? "actor_required"
                : "permission",
        },
        cause: { config },
      };
      let out: unknown = Promise.reject(error);
      for (const r of res) out = (out as Promise<unknown>).catch(r);
      return out;
    },
  };
  return { http: http as unknown as HttpLike & { request(c: Cfg): Promise<unknown> }, sent };
}

const cfg = (url: string): Cfg => {
  const headers = new Map<string, string>([["Idempotency-Key", "idem-1"]]) as Cfg["headers"];
  return { url, headers };
};

describe("X-Actor-User-Id (device-auth.md §4)", () => {
  it("applies to /api/v1 except sync and auth; never to root /auth", () => {
    expect(actorHeaderApplies("/api/v1/goods-receipts")).toBe(true);
    expect(actorHeaderApplies("/api/v1/cash-movements?x=1")).toBe(true);
    expect(actorHeaderApplies("/api/v1/sync/push")).toBe(false);
    expect(actorHeaderApplies("/api/v1/auth/csrf")).toBe(false);
    expect(actorHeaderApplies("/auth/pin/verify")).toBe(false);
  });

  it("sets the cashier on the request; none without a cashier", async () => {
    let actor: string | null = "u-cashier";
    const { http, sent } = fakeHttp(["ok", "ok"]);
    installActorBinding(http, { actor: () => actor, reverify: () => Promise.resolve(true) });
    await http.request(cfg("/api/v1/transfers"));
    actor = null;
    await http.request(cfg("/api/v1/transfers"));
    expect(sent.map((s) => s.actor)).toEqual(["u-cashier", undefined]);
  });

  it("actor_not_verified → PIN re-prompt → same request retried once with the same Idempotency-Key", async () => {
    const prompts: string[] = [];
    const { http, sent } = fakeHttp(["not_verified", "ok"]);
    installActorBinding(http, {
      actor: () => "u-1",
      reverify: (u) => (prompts.push(u), Promise.resolve(true)),
    });
    await expect(http.request(cfg("/api/v1/stock-counts"))).resolves.toEqual({ data: "done" });
    expect(prompts).toEqual(["u-1"]);
    expect(sent).toHaveLength(2);
    expect(sent[1]?.key).toBe("idem-1");
  });

  it("cancelled prompt, a second 403 or another 403 reason → the error reaches the screen", async () => {
    const a = fakeHttp(["not_verified"]);
    installActorBinding(a.http, { actor: () => "u-1", reverify: () => Promise.resolve(false) });
    await expect(a.http.request(cfg("/api/v1/x"))).rejects.toMatchObject({
      params: { reason: "actor_not_verified" },
    });
    const b = fakeHttp(["not_verified", "not_verified"]);
    installActorBinding(b.http, { actor: () => "u-1", reverify: () => Promise.resolve(true) });
    await expect(b.http.request(cfg("/api/v1/x"))).rejects.toMatchObject({ code: "PERMISSION_DENIED" });
    expect(b.sent).toHaveLength(2);
    const c = fakeHttp(["forbidden"]);
    let asked = 0;
    installActorBinding(c.http, { actor: () => "u-1", reverify: () => (asked++, Promise.resolve(true)) });
    await expect(c.http.request(cfg("/api/v1/x"))).rejects.toMatchObject({
      params: { reason: "permission" },
    });
    expect(asked).toBe(0);
  });

  it("SEC-04: reads carry the header too; actor_required also re-prompts", async () => {
    const prompts: string[] = [];
    const { http, sent } = fakeHttp(["required", "ok"]);
    installActorBinding(http, {
      actor: () => "u-1",
      reverify: (u) => (prompts.push(u), Promise.resolve(true)),
    });
    await http.request({ ...cfg("/api/v1/sales?number=K-1"), method: "get" });
    expect(sent.map((x) => x.actor)).toEqual(["u-1", "u-1"]);
    expect(prompts).toEqual(["u-1"]);
  });
});
