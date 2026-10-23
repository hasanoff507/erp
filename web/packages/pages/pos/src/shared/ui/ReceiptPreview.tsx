/**
 * `ReceiptPreview` (08 §13.1): the receipt layout of @shared/lib/receipt drawn with React elements only
 * (no innerHTML, no inline styles — CSP-safe), monospace columns as on paper, QR as SVG rects.
 */
import { useMemo } from "react";

import { encodeQr, layoutReceipt, type PaperWidth, type ReceiptDoc } from "@shared/lib/receipt";
import { cn } from "@shared/ui";

export function QrCode({ data, size = 160, label }: { data: string; size?: number; label?: string }) {
  const qr = useMemo(() => encodeQr(data), [data]);
  const border = 4;
  const dim = qr.size + border * 2;
  const cells: { x: number; y: number }[] = [];
  for (let y = 0; y < qr.size; y += 1)
    for (let x = 0; x < qr.size; x += 1) if (qr.isDark(x, y)) cells.push({ x: x + border, y: y + border });
  return (
    <svg
      viewBox={`0 0 ${dim} ${dim}`}
      width={size}
      height={size}
      role="img"
      aria-label={label ?? data}
      shapeRendering="crispEdges"
      className="bg-white"
    >
      {cells.map((c) => (
        <rect key={`${c.x}-${c.y}`} x={c.x} y={c.y} width={1} height={1} fill="#000" />
      ))}
    </svg>
  );
}

export function ReceiptPreview({ doc, paperWidth = 80 }: { doc: ReceiptDoc; paperWidth?: PaperWidth }) {
  const layout = useMemo(() => layoutReceipt(doc, { paperWidth }), [doc, paperWidth]);
  return (
    <div
      data-testid="receipt-preview"
      className={cn(
        "mx-auto flex flex-col bg-white px-4 py-5 font-mono text-[12px] leading-[1.35] text-black shadow-raised",
        paperWidth === 58 ? "w-[300px]" : "w-[400px]",
      )}
    >
      {layout.blocks.map((b, i) => {
        if (b.type === "rule") return <div key={i} className="my-1 border-t border-dashed border-black/60" />;
        if (b.type === "feed") return <div key={i} className="h-3" />;
        if (b.type === "qr")
          return (
            <div key={i} className="my-2 flex justify-center">
              <QrCode data={b.data} size={120} />
            </div>
          );
        return (
          <div
            key={i}
            className={cn(
              "flex gap-2 whitespace-pre-wrap",
              b.align === "center" && "justify-center text-center",
              b.align === "right" && "justify-end text-right",
              b.bold && "font-bold",
              b.size === "large" && "text-[15px]",
              b.size === "small" && "text-[10px]",
            )}
          >
            <span className="min-w-0 flex-1">{b.left}</span>
            {b.right ? <span className="shrink-0">{b.right}</span> : null}
          </div>
        );
      })}
    </div>
  );
}
