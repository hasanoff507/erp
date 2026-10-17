/**
 * HTML receipt — system printer (`system_print`, 24 §6.1) and electronic receipt / preview.
 * CSP-safe (24 §4.4): no inline `<style>`/`style=` markup — `renderReceiptHtml` returns class-based markup,
 * `renderReceiptElement` builds DOM nodes and styles them through CSSOM (`element.style.*`), which CSP allows.
 * Text is never assigned via innerHTML (no injection from product names).
 */
import { encodeQr, qrSvg } from "./qr.ts";
import type { ReceiptLayout, TextBlock } from "./types.ts";

/** Visible text keeps Uzbek letters (fonts have them), only ʻ → ' like on paper (POS-16 rule). */
const show = (s: string) => s.replace(/[ʻʼ]/gu, "'");

const escapeHtml = (s: string) =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

/** Class-based HTML (preview / e-receipt export). Classes: erp-receipt, erp-receipt__row, --small, --large … */
export function renderReceiptHtml(layout: ReceiptLayout): string {
  const parts: string[] = [`<div class="erp-receipt erp-receipt--${layout.paperWidth}mm">`];
  for (const block of layout.blocks) {
    if (block.type === "rule") parts.push(`<hr class="erp-receipt__rule">`);
    else if (block.type === "feed") continue;
    else if (block.type === "qr") parts.push(`<div class="erp-receipt__qr">${qrSvg(block.data)}</div>`);
    else {
      const cls = [
        "erp-receipt__row",
        `erp-receipt__row--${block.align}`,
        block.size !== "normal" ? `erp-receipt__row--${block.size}` : "",
        block.bold ? "erp-receipt__row--bold" : "",
      ]
        .filter(Boolean)
        .join(" ");
      const right = block.right
        ? `<span class="erp-receipt__right">${escapeHtml(show(block.right))}</span>`
        : "";
      parts.push(
        `<div class="${cls}"><span class="erp-receipt__left">${escapeHtml(show(block.left))}</span>${right}</div>`,
      );
    }
  }
  parts.push("</div>");
  return parts.join("");
}

const FONT = "'Manrope Variable', 'Noto Sans Variable', 'Segoe UI', Arial, sans-serif";

function rowElement(doc: Document, block: TextBlock): HTMLElement {
  const row = doc.createElement("div");
  row.style.display = "flex";
  row.style.justifyContent = block.right
    ? "space-between"
    : block.align === "center"
      ? "center"
      : block.align === "right"
        ? "flex-end"
        : "flex-start";
  row.style.gap = "2mm";
  row.style.fontSize = block.size === "small" ? "8pt" : block.size === "large" ? "13pt" : "10pt";
  row.style.fontWeight = block.bold ? "700" : "400";
  row.style.textAlign = block.align;
  row.style.lineHeight = "1.3";
  const left = doc.createElement("span");
  left.textContent = show(block.left);
  left.style.whiteSpace = "pre-wrap";
  left.style.overflowWrap = "anywhere";
  row.append(left);
  if (block.right) {
    const right = doc.createElement("span");
    right.textContent = show(block.right);
    right.style.whiteSpace = "nowrap";
    right.style.textAlign = "right";
    row.append(right);
  }
  return row;
}

function qrElement(doc: Document, data: string): HTMLElement {
  const qr = encodeQr(data);
  const wrap = doc.createElement("div");
  wrap.style.display = "flex";
  wrap.style.justifyContent = "center";
  wrap.style.padding = "2mm 0";
  const svgNs = "http://www.w3.org/2000/svg";
  const svg = doc.createElementNS(svgNs, "svg");
  const border = 4;
  const dim = qr.size + border * 2;
  svg.setAttribute("viewBox", `0 0 ${dim} ${dim}`);
  svg.setAttribute("width", "32mm");
  svg.setAttribute("height", "32mm");
  svg.setAttribute("shape-rendering", "crispEdges");
  let d = "";
  for (let y = 0; y < qr.size; y += 1) {
    for (let x = 0; x < qr.size; x += 1) if (qr.isDark(x, y)) d += `M${x + border},${y + border}h1v1h-1z`;
  }
  const path = doc.createElementNS(svgNs, "path");
  path.setAttribute("d", d);
  path.setAttribute("fill", "#000");
  svg.append(path);
  wrap.append(svg);
  return wrap;
}

/** DOM receipt for `window.print()` (styles via CSSOM only). Width: 48 mm / 72 mm printable area. */
export function renderReceiptElement(layout: ReceiptLayout, doc: Document): HTMLElement {
  const root = doc.createElement("div");
  root.style.width = layout.paperWidth === 58 ? "48mm" : "72mm";
  root.style.fontFamily = FONT;
  root.style.color = "#000";
  root.style.background = "#fff";
  for (const block of layout.blocks) {
    if (block.type === "rule") {
      const hr = doc.createElement("div");
      hr.style.borderTop = "1px dashed #000";
      hr.style.margin = "1.5mm 0";
      root.append(hr);
    } else if (block.type === "qr") root.append(qrElement(doc, block.data));
    else if (block.type === "feed") continue;
    else root.append(rowElement(doc, block));
  }
  return root;
}
