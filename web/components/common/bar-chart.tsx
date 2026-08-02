import { cn } from "@/lib/utils";
import type { ChartDatum, ChartTone } from "@/types/charts";

const barToneClasses: Record<ChartTone, string> = {
  primary: "bg-primary",
  highlight: "bg-highlight",
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
};

interface BarChartProps {
  data: ChartDatum[];
  tone?: ChartTone;
  /** Accessible summary of what the chart shows. */
  ariaLabel: string;
  /** Formats the value shown in each bar's tooltip/label. */
  formatValue?: (value: number) => string;
  className?: string;
}

/**
 * Token-themed CSS bar chart (flex columns — no SVG needed). Data always
 * arrives via props; heights are percentages of the series maximum.
 */
export function BarChart({
  data,
  tone = "primary",
  ariaLabel,
  formatValue = (value) => String(value),
  className,
}: BarChartProps) {
  const max = Math.max(1, ...data.map((datum) => datum.value));

  return (
    <figure className={cn("w-full", className)}>
      <div
        role="img"
        aria-label={ariaLabel}
        className="flex h-32 items-end gap-1.5 sm:h-40 sm:gap-2"
      >
        {data.map((datum) => (
          <div
            key={datum.label}
            className="group relative flex h-full flex-1 items-end"
            title={`${datum.label}: ${formatValue(datum.value)}`}
          >
            <div
              className={cn(
                "w-full rounded-t-sm transition-opacity group-hover:opacity-80",
                barToneClasses[tone],
              )}
              style={{ height: `${Math.max(2, (datum.value / max) * 100)}%` }}
            />
          </div>
        ))}
      </div>
      <figcaption className="mt-1.5 flex gap-1.5 text-[11px] text-muted-foreground sm:gap-2">
        {data.map((datum, index) => (
          <span
            key={datum.label}
            className={cn(
              "flex-1 truncate text-center",
              // Keep the flex slot so captions stay aligned under their bars.
              index % 2 === 1 && "invisible sm:visible",
            )}
          >
            {datum.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
