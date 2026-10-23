import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { initI18n } from "@shared/i18n";

import { isChunkLoadError, RouteErrorPage } from "./RouteErrorPage.tsx";

beforeAll(() => {
  initI18n("uz");
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

describe("RouteErrorPage (route errorElement)", () => {
  it("catches a render error, shows the translated state and retries in place", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    let fail = true;
    function Flaky() {
      if (fail) throw new Error("boom: raw details");
      return <p>recovered</p>;
    }
    const router = createMemoryRouter(
      [{ path: "/app", element: <Flaky />, errorElement: <RouteErrorPage /> }],
      { initialEntries: ["/app"] },
    );
    render(<RouterProvider router={router} />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Sahifani ochib bo'lmadi")).toBeInTheDocument();
    expect(screen.queryByText(/boom/)).toBeNull();

    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Qayta urinish" }));
    expect(await screen.findByText("recovered")).toBeInTheDocument();
  });

  it("a failed lazy chunk reloads the page once, then offers a manual reload", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const reload = vi.fn();
    vi.spyOn(window, "location", "get").mockReturnValue({ ...window.location, reload });
    const lazyFails = () =>
      createMemoryRouter(
        [
          {
            path: "/pos",
            lazy: () =>
              Promise.reject(new TypeError("Failed to fetch dynamically imported module: /assets/x.js")),
            errorElement: <RouteErrorPage />,
          },
        ],
        { initialEntries: ["/pos"] },
      );

    render(<RouterProvider router={lazyFails()} />);
    expect(
      await screen.findByText("Ilovaning yangi versiyasi chiqqan.", { exact: false }),
    ).toBeInTheDocument();
    expect(reload).toHaveBeenCalledTimes(1);
    cleanup();

    // Second failure within 30 s: no automatic reload loop, the button is there instead.
    render(<RouterProvider router={lazyFails()} />);
    const button = await screen.findByRole("button", { name: "Sahifani qayta yuklash" });
    expect(reload).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Qayta urinish" })).toBeNull();
    fireEvent.click(button);
    expect(reload).toHaveBeenCalledTimes(2);
  });

  it("recognises chunk-load errors of the major browsers", () => {
    expect(isChunkLoadError(new TypeError("Failed to fetch dynamically imported module: x"))).toBe(true);
    expect(isChunkLoadError(new TypeError("error loading dynamically imported module"))).toBe(true);
    expect(isChunkLoadError(new TypeError("Importing a module script failed."))).toBe(true);
    expect(isChunkLoadError(new Error("Unable to preload CSS for /assets/a.css"))).toBe(true);
    expect(isChunkLoadError(new Error("Cannot read properties of undefined"))).toBe(false);
    expect(isChunkLoadError("Failed to fetch dynamically imported module")).toBe(false);
  });
});
