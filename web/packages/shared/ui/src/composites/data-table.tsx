/**
 * DataTable — 08 §7.2 (`DataTable.Compact` preset), §7.4 "Jadval", §10 band 6; 17 §4 pagination.
 *
 * Server-driven: the page model owns sorting/filtering/paging (effector) and passes `data` + state.
 * - semantic <table>; header row bg-muted text-caption; rows min-h 52px, border-divider;
 *   `numeric` columns right-aligned, tabular-nums, extrabold (08 §4.3 meta.numeric);
 * - states (06 §1–§3): `loading` (skeleton rows, aria-busy), `error` (ErrorState + retry), empty
 *   (EmptyState or `empty` node); a refresh with data keeps rows visible (aria-busy only);
 * - row actions menu (DropdownMenu, kebab icon button with aria-label);
 * - `onRowClick`: rows focusable, ↑/↓ move between rows, Enter opens;
 * - pagination: `{ kind: "page", page, size, total, onPageChange }` (reference lists) or
 *   `{ kind: "cursor", hasMore, loadingMore, onLoadMore }` ("Yana yuklash", document registers).
 * Wide tables scroll inside an `overflow-x-auto` box (08 §6.2).
 */
import { ChevronLeft, ChevronRight, EllipsisVertical, Inbox } from "lucide-react";
import type { KeyboardEvent, ReactNode } from "react";

import { useTranslation } from "@shared/i18n";

import { Button } from "#/components/ui/button.tsx";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "#/components/ui/dropdown-menu.tsx";
import { Skeleton } from "#/components/ui/skeleton.tsx";
import { Icon, type LucideIcon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

import { EmptyState, ErrorState } from "./states.tsx";

export interface DataTableColumn<T> {
  id: string;
  header: ReactNode;
  cell: (row: T, index: number) => ReactNode;
  /** Money / qty / count column: right-aligned, tabular-nums, extrabold. */
  numeric?: boolean;
  /** Fixed CSS width of the column, e.g. "150px" or "20%". */
  width?: string;
  className?: string;
  /** Visually hidden header (e.g. avatar column) — still announced. */
  hideHeader?: boolean;
}

export interface DataTableRowAction<T> {
  id: string;
  label: string;
  icon?: LucideIcon;
  onSelect: (row: T) => void;
  destructive?: boolean;
  disabled?: boolean;
}

export type DataTablePagination =
  | { kind: "page"; page: number; size: number; total: number; onPageChange: (page: number) => void }
  | { kind: "cursor"; hasMore: boolean; loadingMore?: boolean; onLoadMore: () => void };

export type DataTableStatus = "idle" | "loading" | "error";

export interface DataTableProps<T> {
  /** Accessible name of the table (e.g. "Xodimlar"). */
  label: string;
  columns: readonly DataTableColumn<T>[];
  data: readonly T[];
  getRowId: (row: T) => string;
  status?: DataTableStatus;
  /** Translated error message for `status="error"`. */
  errorMessage?: string;
  onRetry?: () => void;
  /** Empty state (default: Inbox icon + "Ma'lumot yo'q"). */
  empty?: ReactNode;
  /** Actions per row; return [] to hide the menu for a row. */
  rowActions?: (row: T) => readonly DataTableRowAction<T>[];
  onRowClick?: (row: T) => void;
  selectedRowId?: string | null;
  pagination?: DataTablePagination;
  /** Minimum table width before horizontal scroll (default 640px). */
  minWidth?: number;
  skeletonRows?: number;
  className?: string;
}

function focusSibling(current: HTMLElement, direction: 1 | -1): void {
  const sibling = direction === 1 ? current.nextElementSibling : current.previousElementSibling;
  if (sibling instanceof HTMLElement && sibling.tabIndex >= 0) sibling.focus();
}

export function DataTable<T>({
  label,
  columns,
  data,
  getRowId,
  status = "idle",
  errorMessage,
  onRetry,
  empty,
  rowActions,
  onRowClick,
  selectedRowId,
  pagination,
  minWidth = 640,
  skeletonRows = 5,
  className,
}: DataTableProps<T>) {
  const { t } = useTranslation("common");
  const loading = status === "loading";
  const hasActions = rowActions !== undefined;
  const colCount = columns.length + (hasActions ? 1 : 0);

  const onRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (event.target !== event.currentTarget) return;
    if (event.key === "Enter") {
      event.preventDefault();
      onRowClick?.(row);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      focusSibling(event.currentTarget, 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusSibling(event.currentTarget, -1);
    }
  };

  let body: ReactNode;
  if (status === "error") {
    body = (
      <tr>
        <td colSpan={colCount}>
          <ErrorState
            message={errorMessage ?? t("errors.internal_error")}
            onRetry={onRetry}
            retryable={!!onRetry}
          />
        </td>
      </tr>
    );
  } else if (loading && data.length === 0) {
    body = Array.from({ length: skeletonRows }, (_, i) => (
      <tr key={`skeleton-${i}`} className="border-t border-divider">
        {Array.from({ length: colCount }, (_unused, j) => (
          <td key={j} className="h-[52px] px-5">
            <Skeleton className="h-4 w-3/4" />
          </td>
        ))}
      </tr>
    ));
  } else if (data.length === 0) {
    body = (
      <tr>
        <td colSpan={colCount}>{empty ?? <EmptyState icon={Inbox} title={t("states.empty")} />}</td>
      </tr>
    );
  } else {
    body = data.map((row, index) => {
      const id = getRowId(row);
      const actions = rowActions?.(row) ?? [];
      return (
        <tr
          key={id}
          tabIndex={onRowClick ? 0 : undefined}
          data-selected={selectedRowId === id ? "true" : undefined}
          onClick={onRowClick ? () => onRowClick(row) : undefined}
          onKeyDown={onRowClick ? (e) => onRowKeyDown(e, row) : undefined}
          className={cn(
            "border-t border-divider text-body",
            onRowClick &&
              "cursor-pointer hover:bg-muted focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
            selectedRowId === id && "bg-primary-soft/40",
          )}
        >
          {columns.map((col) => (
            <td
              key={col.id}
              className={cn(
                "h-[52px] px-5 py-2 align-middle",
                col.numeric && "text-right font-extrabold tabular-nums",
                col.className,
              )}
            >
              {col.cell(row, index)}
            </td>
          ))}
          {hasActions ? (
            <td className="h-[52px] w-14 px-3 text-right" onClick={(e) => e.stopPropagation()}>
              {actions.length > 0 ? (
                <DropdownMenu modal={false}>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-9 w-9 px-0"
                      aria-label={t("ui.table.rowActions")}
                    >
                      <Icon as={EllipsisVertical} size="md" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {actions.map((a) => (
                      <DropdownMenuItem
                        key={a.id}
                        disabled={a.disabled}
                        onSelect={() => a.onSelect(row)}
                        className={cn(a.destructive && "text-destructive focus:text-destructive")}
                      >
                        {a.icon ? <Icon as={a.icon} size="sm" /> : null}
                        {a.label}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
            </td>
          ) : null}
        </tr>
      );
    });
  }

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table
          aria-label={label}
          aria-busy={loading || undefined}
          className={cn("w-full border-collapse", loading && data.length > 0 && "opacity-60")}
          style={{ minWidth }}
        >
          <thead>
            <tr className="bg-muted">
              {columns.map((col) => (
                <th
                  key={col.id}
                  scope="col"
                  style={col.width ? { width: col.width } : undefined}
                  className={cn(
                    "px-5 py-3 text-left text-caption font-semibold text-muted-foreground",
                    col.numeric && "text-right",
                  )}
                >
                  {col.hideHeader ? <span className="sr-only">{col.header}</span> : col.header}
                </th>
              ))}
              {hasActions ? (
                <th scope="col" className="w-14 px-3 py-3">
                  <span className="sr-only">{t("ui.table.actions")}</span>
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>{body}</tbody>
        </table>
      </div>
      {pagination && status !== "error" ? <DataTablePager pagination={pagination} loading={loading} /> : null}
    </div>
  );
}

function DataTablePager({ pagination, loading }: { pagination: DataTablePagination; loading: boolean }) {
  const { t } = useTranslation("common");
  if (pagination.kind === "cursor") {
    if (!pagination.hasMore) return null;
    return (
      <div className="flex justify-center">
        <Button
          variant="secondary"
          size="sm"
          onClick={pagination.onLoadMore}
          disabled={pagination.loadingMore === true || loading}
          aria-busy={pagination.loadingMore || undefined}
        >
          {t("ui.table.loadMore")}
        </Button>
      </div>
    );
  }
  const { page, size, total, onPageChange } = pagination;
  if (total === 0) return null;
  const pages = Math.max(1, Math.ceil(total / size));
  const from = (page - 1) * size + 1;
  const to = Math.min(page * size, total);
  return (
    <nav aria-label={t("ui.table.pagination")} className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-small tabular-nums text-muted-foreground">
        {t("ui.table.range", { from, to, total })}
      </span>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          className="w-9 px-0"
          aria-label={t("ui.table.prevPage")}
          disabled={page <= 1 || loading}
          onClick={() => onPageChange(page - 1)}
        >
          <Icon as={ChevronLeft} size="sm" />
        </Button>
        <span className="min-w-14 text-center text-small font-semibold tabular-nums" aria-current="page">
          {t("ui.table.pageOf", { page, pages })}
        </span>
        <Button
          variant="secondary"
          size="sm"
          className="w-9 px-0"
          aria-label={t("ui.table.nextPage")}
          disabled={page >= pages || loading}
          onClick={() => onPageChange(page + 1)}
        >
          <Icon as={ChevronRight} size="sm" />
        </Button>
      </div>
    </nav>
  );
}
