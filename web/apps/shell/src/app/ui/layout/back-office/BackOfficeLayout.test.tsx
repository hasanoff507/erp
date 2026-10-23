import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import { initI18n } from "@shared/i18n";

import { BackOfficeLayout } from "./BackOfficeLayout.tsx";
import { trapTab } from "./focus-trap.ts";

beforeAll(() => {
  initI18n("uz");
});

afterEach(() => {
  cleanup();
});

function renderLayout() {
  const router = createMemoryRouter(
    [{ path: "/app", element: <BackOfficeLayout />, children: [{ index: true, element: <p>content</p> }] }],
    { initialEntries: ["/app"] },
  );
  render(<RouterProvider router={router} />);
}

describe("BackOfficeLayout mobile drawer (role=dialog, aria-modal)", () => {
  it("focus goes into the drawer, Tab cycles inside it, Escape returns focus to the burger", () => {
    renderLayout();
    const burger = screen.getByRole("button", { name: "Menyuni ochish" });
    burger.focus();
    fireEvent.click(burger);

    const dialog = screen.getByRole("dialog");
    const close = screen.getAllByRole("button", { name: "Menyuni yopish" });
    const last = close[close.length - 1];
    expect(document.activeElement).toBe(last);

    // Tab on the last focusable element wraps to the first one inside the dialog.
    fireEvent.keyDown(window, { key: "Tab" });
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).not.toBe(last);
    // Shift+Tab from the first wraps back to the last.
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(burger);
  });

  it("the close button also restores focus to the burger", () => {
    renderLayout();
    const burger = screen.getByRole("button", { name: "Menyuni ochish" });
    burger.focus();
    fireEvent.click(burger);
    const close = screen.getAllByRole("button", { name: "Menyuni yopish" });
    fireEvent.click(close[close.length - 1] as HTMLElement);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(burger);
  });
});

describe("trapTab", () => {
  it("wraps at the ends, brings outside focus back in, ignores other keys", () => {
    const box = document.createElement("div");
    box.innerHTML = '<button id="a">a</button><a id="b" href="/x">b</a><button id="c" disabled>c</button>';
    const outside = document.createElement("button");
    document.body.append(box, outside);
    const a = box.querySelector<HTMLElement>("#a");
    const b = box.querySelector<HTMLElement>("#b");

    b?.focus();
    expect(trapTab(box, { key: "Tab", shiftKey: false })).toBe(a);
    a?.focus();
    expect(trapTab(box, { key: "Tab", shiftKey: true })).toBe(b);
    expect(trapTab(box, { key: "Tab", shiftKey: false })).toBeNull();
    outside.focus();
    expect(trapTab(box, { key: "Tab", shiftKey: false })).toBe(a);
    expect(trapTab(box, { key: "Enter", shiftKey: false })).toBeNull();
    box.remove();
    outside.remove();
  });
});
