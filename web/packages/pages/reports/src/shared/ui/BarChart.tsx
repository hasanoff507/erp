/**
 * Column chart (08 charts — recharts, 24 §4; mockup Bo02Dashboard «Savdo — oxirgi 7 kun»): value label
 * above each column, day label below; the highlighted column (today) is `primary`, the rest
 * `primary-soft-border`. Colours come from Tailwind classes on the SVG shapes (CSS `fill` wins over
 * the attribute), so the theme tokens apply; recharts styles only through React's style prop (CSSOM) —
 * nothing the strict CSP blocks. Screen readers get the values as a list.
 */
import { Bar, BarChart as Chart, Cell, LabelList, ResponsiveContainer, XAxis } from "recharts";

import { cn } from "@shared/ui";

import { chartPoints, type ChartBarInput } from "../lib/chart.ts";

export interface BarChartProps {
  bars: readonly ChartBarInput[];
  /** Accessible name of the chart (its title). */
  label: string;
  /** Value label above a bar (e.g. «mln so'm» short form). */
  formatValue: (value: string) => string;
  /** Full value for screen readers. */
  formatFull: (value: string) => string;
  className?: string;
}

export function BarChart({ bars, label, formatValue, formatFull, className }: BarChartProps) {
  const points = chartPoints(bars);
  return (
    <figure className={cn("flex flex-col", className)} aria-label={label}>
      <ul className="sr-only">
        {bars.map((b) => (
          <li key={b.key}>
            {b.label}: {formatFull(b.value)}
          </li>
        ))}
      </ul>
      <div aria-hidden="true" className="h-[260px] w-full" data-testid="bar-chart">
        <ResponsiveContainer width="100%" height="100%">
          <Chart data={points} margin={{ top: 24, right: 6, bottom: 0, left: 6 }} barCategoryGap="22%">
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={{ className: "stroke-border" }}
              tick={{ className: "fill-muted-foreground text-[12px]" }}
              interval={0}
            />
            <Bar dataKey="amount" radius={[10, 10, 4, 4]} maxBarSize={46} isAnimationActive={false}>
              {points.map((p) => (
                <Cell key={p.key} className={p.highlight ? "fill-primary" : "fill-primary-soft-border"} />
              ))}
              <LabelList
                dataKey="value"
                position="top"
                className="fill-foreground-secondary text-[12px] font-bold"
                formatter={(v: unknown) => (typeof v === "string" ? formatValue(v) : "")}
              />
            </Bar>
          </Chart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
