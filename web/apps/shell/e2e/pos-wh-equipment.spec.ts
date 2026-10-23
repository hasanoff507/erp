/**
 * POS-16 Uskunalar (b3-pos-wh) — QT-M01-22: printer chosen through Web Serial (navigator.serial mocked in the
 * page), «Sinov chek» sends ESC/POS with cp866 (`ESC t 17`) and — because the text has Қ/Ғ/Ҳ — raster bands
 * (`GS v 0`); the setting is device-local (erp-device) and survives a reload; scale templates are shown read-only
 * and a scanned weight label is decoded (22 → 1,250 kg).
 */
import { expect, test } from "@playwright/test";

import { installSyncStub } from "./support/offline-stub.ts";
import { scanCode, seedWarehousePos, whPull, whSession } from "./support/pos-wh-seed.ts";

declare global {
  interface Window {
    __printed: number[];
  }
}

test("QT-M01-22 Web Serial test receipt: cp866 + raster for Қ/Ғ/Ҳ, setting kept on the device", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.__printed = [];
    let granted = false;
    const port = {
      writable: {
        getWriter: () => ({
          write: (chunk: Uint8Array) => {
            window.__printed.push(...chunk);
            return Promise.resolve();
          },
          releaseLock: () => undefined,
        }),
      },
      open: () => Promise.resolve(),
      close: () => Promise.resolve(),
    };
    Object.defineProperty(navigator, "serial", {
      configurable: true,
      value: {
        getPorts: () => Promise.resolve(granted ? [port] : []),
        requestPort: () => {
          granted = true;
          return Promise.resolve(port);
        },
      },
    });
  });
  const sync = await installSyncStub(page, { session: whSession(), pull: whPull() });
  await seedWarehousePos(page, sync, "/pos/settings/devices");
  await expect(page.getByTestId("pos-equipment")).toBeVisible();

  await page.getByTestId("printer-detect").click();
  await expect(page.getByTestId("transport-webserial")).toHaveAttribute("data-state", "checked");
  await page.getByTestId("printer-test").click();
  await expect(page.getByTestId("printer-test-result")).toContainText("raster");

  const bytes = await page.evaluate(() => window.__printed);
  const has = (needle: number[]) => bytes.some((_, i) => needle.every((b, j) => bytes[i + j] === b));
  expect(has([0x1b, 0x40])).toBe(true); // ESC @ init
  expect(has([0x1b, 0x74, 0x11])).toBe(true); // ESC t 17 = cp866
  expect(has([0x1d, 0x76, 0x30])).toBe(true); // GS v 0 raster (Қ/Ғ/Ҳ in «Ўзбекистон Қўқон Ғалла Ҳисоб»)
  expect(has([0x1d, 0x56])).toBe(true); // GS V cut

  // Enter on a focused button activates that button (POS hotkey rule) — move focus off the buttons first
  await page.getByRole("heading", { name: "Uskunalar sozlamasi" }).click();
  await page.keyboard.press("Enter"); // «Saqlash»
  await expect(page.getByText("Sozlama saqlandi")).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("transport-webserial")).toHaveAttribute("data-state", "checked");

  // scale templates (read-only) + scanner test decodes a weight label
  await expect(page.getByTestId("equipment-scale")).toContainText("Og'irlik (gramm)");
  await expect(page.getByTestId("equipment-scale")).toContainText("Faqat ko'rish");
  await page.getByTestId("equipment-scale").click(); // focus away from inputs
  await scanCode(page, "2212345012503");
  await expect(page.getByTestId("scanner-result")).toContainText("Tarozi yorlig'i");
  await expect(page.getByTestId("scanner-result")).toContainText("1.25 kg");
});
