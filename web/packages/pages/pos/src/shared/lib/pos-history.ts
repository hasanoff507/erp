/**
 * In-tab history of visited /pos routes (UX-09): POS-11 / POS-12 «Orqaga» (Esc) returns to the screen the
 * cashier came from; without one — POS-02 for a seller, the warehouse hub for a storekeeper.
 */
let visited: string[] = [];

export function recordPosPath(pathname: string): void {
  if (!pathname.startsWith("/pos")) return;
  if (visited[visited.length - 1] === pathname) return;
  visited = [...visited.slice(-19), pathname];
}

/** The /pos route visited before `current`, or null. */
export function previousPosPath(current: string): string | null {
  for (let i = visited.length - 1; i >= 0; i -= 1) {
    const path = visited[i];
    if (path && path !== current) return path;
  }
  return null;
}

/** Where «Orqaga» goes from POS-11 / POS-12. */
export function posBackTarget(current: string, canSell: boolean): string {
  return previousPosPath(current) ?? (canSell ? "/pos/sale" : "/pos/warehouse");
}

export function resetPosHistory(): void {
  visited = [];
}

/** True when an earlier /pos screen of this tab exists — «Orqaga» can step back in the browser history. */
export function hasPosHistory(current: string): boolean {
  return previousPosPath(current) !== null;
}
