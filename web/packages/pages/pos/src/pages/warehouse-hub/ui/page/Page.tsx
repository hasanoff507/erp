/**
 * Ombor — the POS landing of a storekeeper (users without `shift.open`, contracts/pos-wh-routes.md): big tiles to
 * POS-08 «Tovar qabul qilish», POS-09 «Ko'chirish», POS-10 «Inventarizatsiya» (by the cashier's permissions)
 * and POS-16 «Uskunalar», POS-11 «Narx/qoldiq» (`stock.view`, UX-09 — global F9 is off on the warehouse screens).
 * Keys 1…5 open the tiles, Esc goes back.
 */
import {
  ArrowRightLeft,
  ClipboardList,
  PackageCheck,
  Search,
  Settings2,
  type LucideIcon,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { Button, EmptyState, Icon, Kbd } from "@shared/ui";

import { usePosPermission } from "#/entities/pos-session/index.ts";
import { WhScreen } from "#/features/wh-scan/index.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

interface Tile {
  path: string;
  icon: LucideIcon;
  label: string;
}

function WarehouseHubPage() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const receive = usePosPermission("purchases.receive");
  const transferCreate = usePosPermission("transfer.create");
  const transferReceive = usePosPermission("transfer.receive");
  const count = usePosPermission("stock.count.create");
  const lookup = usePosPermission("stock.view");

  const tiles: Tile[] = [
    ...(receive
      ? [{ path: "/pos/warehouse/receive", icon: PackageCheck, label: t("goodsReceipt.title") }]
      : []),
    ...(transferCreate || transferReceive
      ? [{ path: "/pos/warehouse/transfer", icon: ArrowRightLeft, label: t("transfers.title") }]
      : []),
    ...(count
      ? [{ path: "/pos/warehouse/stocktake", icon: ClipboardList, label: t("stockCount.title") }]
      : []),
    { path: "/pos/settings/devices", icon: Settings2, label: t("equipment.title") },
    ...(lookup ? [{ path: "/pos/lookup", icon: Search, label: t("wh.lookupTile") }] : []),
  ];
  const warehouseTiles = tiles.filter((tile) => tile.path.startsWith("/pos/warehouse/")).length;

  useHotkeys([
    ...tiles.map((tile, i) => ({ key: String(i + 1), handler: () => navigate(tile.path) })),
    { key: "Escape", handler: () => navigate(-1) },
  ]);

  return (
    <WhScreen
      title={t("wh.hubTitle")}
      subtitle={t("wh.hubSubtitle")}
      onBack={() => navigate(-1)}
      testId="pos-warehouse"
    >
      {warehouseTiles === 0 ? <EmptyState icon={ClipboardList} title={t("wh.hubEmpty")} /> : null}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {tiles.map((tile, i) => (
          <Button
            key={tile.path}
            variant="secondary"
            className="flex h-40 flex-col items-center justify-center gap-3 rounded-2xl text-[18px] font-extrabold"
            onClick={() => navigate(tile.path)}
            data-testid={`hub-tile-${tile.path.split("/").pop() ?? ""}`}
          >
            <Icon as={tile.icon} size="lg" />
            {tile.label}
            <Kbd keys={String(i + 1)} />
          </Button>
        ))}
      </div>
    </WhScreen>
  );
}

export const WarehouseHub = {
  route: "warehouse",
  titleKey: "pos:wh.hubTitle",
  Page: WarehouseHubPage,
} as const;
