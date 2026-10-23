/**
 * BO-12 «Karta terminallari» (07 BO-12, 18 §16a.5; qaror #71) — terminals of the selected branch:
 * `GET /card-terminals?branch_id=`, `POST /card-terminals`, `PATCH /card-terminals/{id}` (version).
 * No card data exists here — a terminal is a device record (TID/MID, LAN address, agent device).
 */
import { createEffect, createEvent, createStore, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import type {
  CardTerminalCreate,
  CardTerminalOut,
  CardTerminalPage,
  CardTerminalUpdate,
} from "@shared/models";

export type CardTerminal = CardTerminalOut;
export type { CardTerminalCreate, CardTerminalUpdate };

export const cardTerminalsOpened = createEvent<string>();
export const cardTerminalsReloadRequested = createEvent();

export const fetchCardTerminalsFx = createEffect<string, CardTerminalPage, ApiError>((branchId) =>
  api.cardTerminals.listTerminals({ branch_id: branchId, page: 1, size: 200 }),
);
export const createCardTerminalFx = createEffect<CardTerminalCreate, CardTerminalOut, ApiError>((body) =>
  api.cardTerminals.createTerminal(body),
);
export const updateCardTerminalFx = createEffect<
  { id: string; body: CardTerminalUpdate },
  CardTerminalOut,
  ApiError
>(({ id, body }) => api.cardTerminals.updateTerminal(id, body));

export const $cardTerminalsBranch = createStore<string | null>(null, { skipVoid: false });
export const $cardTerminals = createStore<CardTerminal[]>([]);
export const $cardTerminalsError = createStore<ApiError | null>(null, { skipVoid: false });

$cardTerminalsBranch.on(cardTerminalsOpened, (_, id) => id);
$cardTerminals.reset(cardTerminalsOpened);

sample({ clock: cardTerminalsOpened, target: fetchCardTerminalsFx });
sample({
  clock: [cardTerminalsReloadRequested, createCardTerminalFx.done, updateCardTerminalFx.done],
  source: $cardTerminalsBranch,
  filter: (id): id is string => id !== null,
  target: fetchCardTerminalsFx,
});
$cardTerminals.on(fetchCardTerminalsFx.done, (_, { params, result }) =>
  result.items.filter((t) => t.branch_id === params),
);
$cardTerminalsError.on(fetchCardTerminalsFx.failData, (_, e) => e).reset(fetchCardTerminalsFx.done);

/** Terminals of one register, the default one first (BO-12 «Karta terminali» column). */
export function terminalsOf(terminals: readonly CardTerminal[], registerId: string): CardTerminal[] {
  return terminals
    .filter((t) => t.cash_register_id === registerId && t.status !== "archived")
    .sort((a, b) => (a.is_default === b.is_default ? 0 : a.is_default ? -1 : 1));
}

export const ADAPTERS = ["agent_ecr", "cloud", "android_intent", "softpos", "fake"] as const;
export type Adapter = (typeof ADAPTERS)[number];
const OCTET = "(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])";
const PRIVATE_IPV4 = new RegExp(
  `^(10\\.${OCTET}|172\\.(1[6-9]|2[0-9]|3[01])|192\\.168)\\.${OCTET}\\.${OCTET}$`,
);

/** RFC 1918 IPv4 only (12 `card_terminals` CHECK, 15 §9.3 — no arbitrary hosts). */
export function isPrivateIpv4(value: string): boolean {
  return PRIVATE_IPV4.test(value);
}
