import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Pencil, Trash2 } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { DataTable, type DataTableColumn } from "./data-table.tsx";

interface Branch {
  id: string;
  name: string;
  registers: string;
}

const rows: Branch[] = [
  { id: "b1", name: "Chilonzor-3", registers: "2" },
  { id: "b2", name: "Yunusobod-1", registers: "1" },
  { id: "b3", name: "Sergeli", registers: "0" },
];

const columns: DataTableColumn<Branch>[] = [
  { id: "name", header: "Filial", cell: (r) => r.name },
  { id: "registers", header: "Kassalar", cell: (r) => r.registers, numeric: true },
];

describe("DataTable — 08 §7.4 / 17 §4", () => {
  it("renders a labelled table with headers and right-aligned numeric cells", () => {
    render(<DataTable label="Filiallar" columns={columns} data={rows} getRowId={(r) => r.id} />);
    const table = screen.getByRole("table", { name: "Filiallar" });
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["Filial", "Kassalar"]);
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(screen.getByRole("cell", { name: "2" })).toHaveClass("text-right", "tabular-nums");
  });

  it("loading without data shows skeleton rows and aria-busy", () => {
    render(
      <DataTable
        label="Filiallar"
        columns={columns}
        data={[]}
        getRowId={(r) => r.id}
        status="loading"
        skeletonRows={3}
      />,
    );
    const table = screen.getByRole("table", { name: "Filiallar" });
    expect(table).toHaveAttribute("aria-busy", "true");
    expect(within(table).getAllByRole("row")).toHaveLength(4);
  });

  it("empty shows the default or a custom empty state", () => {
    const { rerender } = render(
      <DataTable label="Filiallar" columns={columns} data={[]} getRowId={(r) => r.id} />,
    );
    expect(screen.getByText("Ma'lumot yo'q")).toBeInTheDocument();
    rerender(
      <DataTable
        label="Filiallar"
        columns={columns}
        data={[]}
        getRowId={(r) => r.id}
        empty={<p>Filial yo'q</p>}
      />,
    );
    expect(screen.getByText("Filial yo'q")).toBeInTheDocument();
  });

  it("error shows a translated message with retry and hides pagination", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <DataTable
        label="Filiallar"
        columns={columns}
        data={[]}
        getRowId={(r) => r.id}
        status="error"
        errorMessage="Internet aloqasi yo'q"
        onRetry={onRetry}
        pagination={{ kind: "page", page: 1, size: 50, total: 3, onPageChange: vi.fn() }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Internet aloqasi yo'q");
    expect(screen.queryByRole("navigation")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Qayta urinish" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("row actions menu runs the chosen action", async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    render(
      <DataTable
        label="Filiallar"
        columns={columns}
        data={rows}
        getRowId={(r) => r.id}
        rowActions={(r) =>
          r.id === "b3"
            ? []
            : [
                { id: "edit", label: "Tahrirlash", icon: Pencil, onSelect: onEdit },
                { id: "archive", label: "Arxivlash", icon: Trash2, onSelect: vi.fn(), destructive: true },
              ]
        }
      />,
    );
    const menus = screen.getAllByRole("button", { name: "Qator amallari" });
    expect(menus).toHaveLength(2);
    await user.click(menus[1] as HTMLElement);
    await user.click(await screen.findByRole("menuitem", { name: "Tahrirlash" }));
    expect(onEdit).toHaveBeenCalledWith(rows[1]);
  });

  it("clickable rows: Enter opens, arrows move focus", async () => {
    const user = userEvent.setup();
    const onRowClick = vi.fn();
    render(
      <DataTable
        label="Filiallar"
        columns={columns}
        data={rows}
        getRowId={(r) => r.id}
        onRowClick={onRowClick}
        selectedRowId="b2"
      />,
    );
    const bodyRows = screen.getAllByRole("row").slice(1);
    expect(bodyRows[1]).toHaveAttribute("data-selected", "true");
    (bodyRows[0] as HTMLElement).focus();
    await user.keyboard("{ArrowDown}");
    expect(bodyRows[1]).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onRowClick).toHaveBeenCalledWith(rows[1]);
    await user.keyboard("{ArrowUp}");
    expect(bodyRows[0]).toHaveFocus();
  });

  it("page pagination shows the range and moves pages", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(
      <DataTable
        label="Tovarlar"
        columns={columns}
        data={rows}
        getRowId={(r) => r.id}
        pagination={{ kind: "page", page: 1, size: 50, total: 437, onPageChange }}
      />,
    );
    const nav = screen.getByRole("navigation", { name: "Sahifalar" });
    expect(nav).toHaveTextContent("1–50, jami 437");
    expect(nav).toHaveTextContent("1 / 9");
    expect(screen.getByRole("button", { name: "Oldingi sahifa" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Keyingi sahifa" }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("cursor pagination shows 'Yana yuklash' only while more pages exist", async () => {
    const user = userEvent.setup();
    const onLoadMore = vi.fn();
    const { rerender } = render(
      <DataTable
        label="Narx tarixi"
        columns={columns}
        data={rows}
        getRowId={(r) => r.id}
        pagination={{ kind: "cursor", hasMore: true, onLoadMore }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Yana yuklash" }));
    expect(onLoadMore).toHaveBeenCalledOnce();
    rerender(
      <DataTable
        label="Narx tarixi"
        columns={columns}
        data={rows}
        getRowId={(r) => r.id}
        pagination={{ kind: "cursor", hasMore: true, loadingMore: true, onLoadMore }}
      />,
    );
    expect(screen.getByRole("button", { name: "Yana yuklash" })).toBeDisabled();
    rerender(
      <DataTable
        label="Narx tarixi"
        columns={columns}
        data={rows}
        getRowId={(r) => r.id}
        pagination={{ kind: "cursor", hasMore: false, onLoadMore }}
      />,
    );
    expect(screen.queryByRole("button", { name: "Yana yuklash" })).toBeNull();
  });
});
