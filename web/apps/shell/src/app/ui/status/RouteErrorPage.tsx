/**
 * Route `errorElement` (root, `/app`, `/pos`) — 08 `ErrorState`: icon + translated message (raw error
 * text never shown) + «Qayta urinish». A failed lazy chunk (deploy replaced the hashed files the
 * running tab still points to) cannot be retried in place: the page reloads once by itself, and if the
 * chunk is still missing the user gets the «Sahifani qayta yuklash» button.
 */
import { RefreshCw, TriangleAlert } from "lucide-react";
import { useEffect } from "react";
import { useLocation, useNavigate, useRouteError } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { Button, Card, EmptyState, Icon } from "@shared/ui";

const CHUNK_ERROR =
  /Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed|Unable to preload CSS|ChunkLoadError|Loading chunk [\w-]+ failed/i;

/** True for "the JS/CSS chunk of this route could not be loaded" (Chromium, Firefox, Safari, Vite). */
export function isChunkLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return error.name === "ChunkLoadError" || CHUNK_ERROR.test(error.message);
}

const RELOAD_MARK = "erp:chunk-reload-at";
const RELOAD_WINDOW_MS = 30_000;

/** Reload once per 30 s at most — never a reload loop when the chunk is really gone. */
function reloadOnceForChunkError(): boolean {
  try {
    const last = new Date(window.sessionStorage.getItem(RELOAD_MARK) ?? "").getTime();
    if (Number.isFinite(last) && Date.now() - last < RELOAD_WINDOW_MS) return false;
    window.sessionStorage.setItem(RELOAD_MARK, new Date().toISOString());
  } catch {
    return false;
  }
  window.location.reload();
  return true;
}

export function RouteErrorPage() {
  const { t } = useTranslation();
  const error = useRouteError();
  const navigate = useNavigate();
  const location = useLocation();
  const chunkError = isChunkLoadError(error);

  useEffect(() => {
    if (chunkError) reloadOnceForChunkError();
  }, [chunkError]);

  useEffect(() => {
    // Diagnostics only (Sentry picks console errors up later); the UI never shows the raw text.
    console.error(error);
  }, [error]);

  const retry = () => {
    // Same URL, new location key: the router re-runs loaders/lazy and resets the render boundary.
    void navigate(`${location.pathname}${location.search}${location.hash}`, { replace: true });
  };

  return (
    <div role="alert" className="flex min-h-dvh items-center justify-center bg-background p-4">
      <Card className="p-0">
        <EmptyState
          icon={TriangleAlert}
          title={t("routeError.title")}
          description={chunkError ? t("routeError.updateBody") : t("routeError.body")}
          action={
            <div className="mt-2 flex flex-wrap justify-center gap-2">
              {chunkError ? null : (
                <Button variant="secondary" onClick={retry}>
                  {t("routeError.retry")}
                </Button>
              )}
              <Button variant={chunkError ? "default" : "outline"} onClick={() => window.location.reload()}>
                <Icon as={RefreshCw} size="md" />
                {t("routeError.reload")}
              </Button>
            </div>
          }
        />
      </Card>
    </div>
  );
}
