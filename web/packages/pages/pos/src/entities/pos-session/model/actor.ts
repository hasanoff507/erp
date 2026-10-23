/**
 * `X-Actor-User-Id` on POS REST calls (contracts/device-auth.md §4): on a device-bound session every
 * `/api/v1` request (writes required, reads allowed) names the PIN-verified cashier; `/api/v1/sync/*` and
 * `/api/v1/auth/*` (and root `/auth/*`) are exempt. The server binds the cashier to the session on an ONLINE
 * `POST /auth/pin/verify` (12 h). `403 PERMISSION_DENIED params.reason="actor_not_verified"` (binding missing
 * — e.g. the PIN was only checked locally offline — or expired) → the cashier types the PIN again online and the
 * SAME request is retried once (same Idempotency-Key, it stays in the request headers).
 *
 * Installed as interceptors on the shared axios instance (`http` of @shared/api) — no change to @shared/api.
 */
/** Structural subset of the axios instance / request config (`http` of @shared/api). */
interface RequestConfig {
  url?: string;
  headers: { set(name: string, value: string): unknown };
}
interface Interceptors<V> {
  use(
    onFulfilled?: ((value: V) => V | Promise<V>) | null,
    onRejected?: ((error: unknown) => unknown) | null,
  ): number;
  eject(id: number): void;
}
export interface HttpLike {
  interceptors: { request: Interceptors<RequestConfig>; response: Interceptors<unknown> };
  request(config: RequestConfig): Promise<unknown>;
}

export const ACTOR_HEADER = "X-Actor-User-Id";

export function actorHeaderApplies(url: string | undefined): boolean {
  if (!url) return false;
  const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0] ?? "";
  if (!path.startsWith("/api/v1/")) return false;
  return !path.startsWith("/api/v1/sync/") && !path.startsWith("/api/v1/auth/");
}

export const isActorNotVerified = (e: unknown): boolean => {
  const err = e as { status?: unknown; code?: unknown; params?: Record<string, unknown> } | null;
  const reason = err?.params?.reason;
  // actor_required: the header did not reach the server (sent before the PIN) — same online PIN, then retry
  return (
    err?.status === 403 &&
    err.code === "PERMISSION_DENIED" &&
    (reason === "actor_not_verified" || reason === "actor_required")
  );
};

type ActorConfig = RequestConfig & { _actorRetried?: boolean };

export interface ActorBinding {
  /** The PIN-verified cashier (null — nobody signed in: no header). */
  actor(): string | null;
  /** Re-prompt the PIN online for this user; true = `/auth/pin/verify` succeeded (binding created). */
  reverify(userId: string): Promise<boolean>;
}

/** Returns an uninstall function. */
export function installActorBinding(http: HttpLike, binding: ActorBinding): () => void {
  const req = http.interceptors.request.use((config) => {
    const actor = binding.actor();
    if (actor && actorHeaderApplies(config.url)) config.headers.set(ACTOR_HEADER, actor);
    return config;
  });
  const res = http.interceptors.response.use(undefined, async (error: unknown) => {
    if (!isActorNotVerified(error)) throw error;
    const config = (error as { cause?: { config?: ActorConfig } }).cause?.config ?? null;
    const actor = binding.actor();
    if (!config || config._actorRetried || !actor) throw error;
    if (!(await binding.reverify(actor))) throw error;
    config._actorRetried = true;
    return http.request(config);
  });
  return () => {
    http.interceptors.request.eject(req);
    http.interceptors.response.eject(res);
  };
}
