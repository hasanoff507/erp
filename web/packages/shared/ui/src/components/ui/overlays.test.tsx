import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "../../composites/confirm-dialog.tsx";

import { Button } from "./button.tsx";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "./dialog.tsx";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "./sheet.tsx";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs.tsx";
import { Toaster, toast } from "./toast.tsx";

describe("Dialog — 08 §7.4", () => {
  it("opens from the trigger, is labelled by its title, closes on Esc and returns focus", async () => {
    const user = userEvent.setup();
    render(
      <Dialog>
        <DialogTrigger asChild>
          <Button>Ochish</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogTitle>Filial qo'shish</DialogTitle>
          <DialogDescription>Izoh</DialogDescription>
        </DialogContent>
      </Dialog>,
    );
    const trigger = screen.getByRole("button", { name: "Ochish" });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Filial qo'shish" });
    expect(dialog).toHaveAttribute("aria-describedby");
    expect(screen.getByRole("button", { name: "Yopish" })).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(trigger).toHaveFocus();
  });
});

describe("Sheet — side form panel", () => {
  it("renders header/body/footer in a labelled dialog and closes with the close button", async () => {
    const user = userEvent.setup();
    render(
      <Sheet>
        <SheetTrigger asChild>
          <Button>Xodim qo'shish</Button>
        </SheetTrigger>
        <SheetContent aria-describedby={undefined}>
          <SheetHeader>
            <SheetTitle>Yangi xodim</SheetTitle>
          </SheetHeader>
          <SheetBody>
            <input aria-label="Ism" />
          </SheetBody>
          <SheetFooter>
            <Button>Saqlash</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>,
    );
    await user.click(screen.getByRole("button", { name: "Xodim qo'shish" }));
    expect(screen.getByRole("dialog", { name: "Yangi xodim" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Yopish" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});

describe("ConfirmDialog — 08 §12 #16", () => {
  function Harness({ onConfirm }: { onConfirm: () => Promise<unknown> }) {
    const [open, setOpen] = useState(true);
    const [error, setError] = useState<string | null>(null);
    return (
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Haqiqatan o'chirasizmi?"
        tone="destructive"
        confirmLabel="O'chirish"
        error={error}
        onConfirm={() =>
          onConfirm().catch((e: unknown) => {
            setError("Xatolik yuz berdi");
            throw e;
          })
        }
      />
    );
  }

  it("is an alertdialog; closes after the promise resolves", async () => {
    const user = userEvent.setup();
    let resolve: () => void = () => undefined;
    const onConfirm = vi.fn(() => new Promise<void>((r) => (resolve = r)));
    render(<Harness onConfirm={onConfirm} />);
    expect(screen.getByRole("alertdialog", { name: "Haqiqatan o'chirasizmi?" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "O'chirish" }));
    expect(screen.getByRole("button", { name: "O'chirish" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Bekor qilish" })).toBeDisabled();
    await act(() => Promise.resolve().then(resolve));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  });

  it("stays open and shows the error when the promise rejects", async () => {
    const user = userEvent.setup();
    render(<Harness onConfirm={() => Promise.reject(new Error("x"))} />);
    await user.click(screen.getByRole("button", { name: "O'chirish" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Xatolik yuz berdi");
    expect(screen.getByRole("alertdialog")).toBeVisible();
    expect(screen.getByRole("button", { name: "O'chirish" })).toBeEnabled();
  });

  it("cancel closes without confirming", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn(() => Promise.resolve());
    render(<Harness onConfirm={onConfirm} />);
    await user.click(screen.getByRole("button", { name: "Bekor qilish" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

describe("Tabs", () => {
  it("switches panels with click and arrow keys", async () => {
    const user = userEvent.setup();
    render(
      <Tabs defaultValue="staff">
        <TabsList aria-label="Bo'lim">
          <TabsTrigger value="staff">Xodimlar</TabsTrigger>
          <TabsTrigger value="roles">Rollar</TabsTrigger>
        </TabsList>
        <TabsContent value="staff">Xodimlar ro'yxati</TabsContent>
        <TabsContent value="roles">Rollar ro'yxati</TabsContent>
      </Tabs>,
    );
    expect(screen.getByRole("tab", { name: "Xodimlar" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Xodimlar ro'yxati");
    await user.click(screen.getByRole("tab", { name: "Xodimlar" }));
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Rollar" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Rollar ro'yxati");
  });
});

describe("toast — single notification mechanism", () => {
  it("shows success politely and errors assertively; close button dismisses", async () => {
    const user = userEvent.setup();
    render(<Toaster />);
    act(() => {
      toast.success("Saqlandi");
      toast.error("Xatolik yuz berdi");
    });
    expect(await screen.findByText("Saqlandi")).toBeVisible();
    expect(screen.getByText("Xatolik yuz berdi")).toBeVisible();
    // Radix announces background toasts politely and foreground ones assertively.
    const statuses = screen.getAllByRole("status");
    expect(statuses.some((s) => s.getAttribute("aria-live") === "assertive")).toBe(true);
    const closeButtons = screen.getAllByRole("button", { name: "Bildirishnomani yopish" });
    await user.click(closeButtons[0] as HTMLElement);
    await waitFor(() => expect(screen.queryByText("Saqlandi")).toBeNull());
    act(() => toast.clear());
  });

  it("keeps at most three toasts", async () => {
    render(<Toaster />);
    act(() => {
      for (const n of [1, 2, 3, 4]) toast.info(`Xabar ${n}`);
    });
    expect(await screen.findByText("Xabar 4")).toBeVisible();
    expect(screen.queryByText("Xabar 1")).toBeNull();
    act(() => toast.clear());
  });
});
