import { cn } from "@/lib/utils";
import type { ChartTone, DonutSegment } from "@/types/charts";

const strokeToneClasses: Record<ChartTone, string> = {
  primary: "stroke-primary",
  highlight: "stroke-highlight",
  success: "stroke-success",
  warning: "stroke-warning",
  destructive: "stroke-destructive",
};

const legendToneClasses: Record<ChartTone, string> = {
  primary: "bg-primary",
  highlight: "bg-highlight",
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
};

const RADIUS = 30;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

interface DonutChartProps {
  segments: DonutSegment[];
  /** Large value in the donut's center, e.g. "98.2%". */
  centerValue: string;
  centerLabel?: string;
  /** Accessible summary of what the chart shows. */
  ariaLabel: string;
  showLegend?: boolean;
  className?: string;
}

/**
 * Token-themed SVG donut chart — extends the landing page's ScoreRadial
 * treatment to multi-segment proportions. Data always arrives via props.
 */
export function DonutChart({
  segments,
  centerValue,
  centerLabel,
  ariaLabel,
  showLegend = true,
  className,
}: DonutChartProps) {
  const total = Math.max(
    1,
    segments.reduce((sum, segment) => sum + segment.value, 0),
  );

  const fractions = segments.map((segment) => segment.value / total);
  const arcs = segments.map((segment, index) => {
    // Cumulative fraction of all preceding segments positions this arc.
    const offset = fractions
      .slice(0, index)
      .reduce((sum, fraction) => sum + fraction, 0);
    return {
      ...segment,
      dasharray: `${(fractions[index]! * CIRCUMFERENCE).toFixed(2)} ${CIRCUMFERENCE.toFixed(2)}`,
      dashoffset: (-offset * CIRCUMFERENCE).toFixed(2),
    };
  });

  return (
    <figure
      className={cn("flex items-center gap-5", className)}
      role="img"
      aria-label={ariaLabel}
    >
      <div className="relative shrink-0">
        <svg viewBox="0 0 72 72" className="size-28 -rotate-90">
          <circle
            cx="36"
            cy="36"
            r={RADIUS}
            fill="none"
            strokeWidth="7"
            className="stroke-muted"
          />
          {arcs.map((arc) => (
            <circle
              key={arc.label}
              cx="36"
              cy="36"
              r={RADIUS}
              fill="none"
              strokeWidth="7"
              strokeDasharray={arc.dasharray}
              strokeDashoffset={arc.dashoffset}
              className={strokeToneClasses[arc.tone]}
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-lg font-semibold tabular-nums">
            {centerValue}
          </span>
          {centerLabel ? (
            <span className="text-[10px] text-muted-foreground">
              {centerLabel}
            </span>
          ) : null}
        </div>
      </div>

      {showLegend ? (
        <ul className="space-y-1.5">
          {segments.map((segment) => (
            <li
              key={segment.label}
              className="flex items-center gap-2 text-xs text-muted-foreground"
            >
              <span
                aria-hidden="true"
                className={cn(
                  "size-2 rounded-full",
                  legendToneClasses[segment.tone],
                )}
              />
              <span className="truncate">{segment.label}</span>
              <span className="ml-auto pl-3 font-mono tabular-nums">
                {segment.value}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </figure>
  );
}
