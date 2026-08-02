import { cn } from "@/lib/utils";
import type { ChartSeries, ChartTone } from "@/types/charts";

const strokeToneClasses: Record<ChartTone, string> = {
  primary: "stroke-primary",
  highlight: "stroke-highlight",
  success: "stroke-success",
  warning: "stroke-warning",
  destructive: "stroke-destructive",
};

const fillToneClasses: Record<ChartTone, string> = {
  primary: "fill-primary/10",
  highlight: "fill-highlight/10",
  success: "fill-success/10",
  warning: "fill-warning/10",
  destructive: "fill-destructive/10",
};

const legendToneClasses: Record<ChartTone, string> = {
  primary: "bg-primary",
  highlight: "bg-highlight",
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
};

const VIEW_WIDTH = 400;
const VIEW_HEIGHT = 120;
const PADDING_Y = 8;

function toPoints(values: number[], max: number): string {
  const usable = VIEW_HEIGHT - PADDING_Y * 2;
  return values
    .map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * VIEW_WIDTH;
      const y = VIEW_HEIGHT - PADDING_Y - (value / max) * usable;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

interface LineChartProps {
  series: ChartSeries[];
  /** X-axis tick labels; first/last always shown, middle ones on wide screens. */
  labels: string[];
  /** Accessible summary of what the chart shows. */
  ariaLabel: string;
  /** Fill the area under the first series. */
  area?: boolean;
  showLegend?: boolean;
  className?: string;
}

/**
 * Token-themed SVG line/area chart. Extends the landing page's TrendChart
 * language (features/marketing/showcase) into a reusable, props-driven
 * component — data always arrives via props, never inline.
 */
export function LineChart({
  series,
  labels,
  ariaLabel,
  area = true,
  showLegend = true,
  className,
}: LineChartProps) {
  const max = Math.max(1, ...series.flatMap((entry) => entry.values));

  return (
    <figure className={cn("w-full", className)}>
      {showLegend && series.length > 1 ? (
        <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1">
          {series.map((entry) => (
            <span
              key={entry.name}
              className="flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <span
                aria-hidden="true"
                className={cn(
                  "size-2 rounded-full",
                  legendToneClasses[entry.tone],
                )}
              />
              {entry.name}
            </span>
          ))}
        </div>
      ) : null}

      <svg
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={ariaLabel}
        className="h-32 w-full sm:h-40"
      >
        {/* Horizontal gridlines at 25/50/75%. */}
        {[0.25, 0.5, 0.75].map((fraction) => {
          const y = PADDING_Y + (VIEW_HEIGHT - PADDING_Y * 2) * fraction;
          return (
            <line
              key={fraction}
              x1="0"
              x2={VIEW_WIDTH}
              y1={y}
              y2={y}
              strokeDasharray="4 6"
              className="stroke-border"
              strokeWidth="1"
            />
          );
        })}

        {area && series[0] ? (
          <polygon
            points={`0,${VIEW_HEIGHT} ${toPoints(series[0].values, max)} ${VIEW_WIDTH},${VIEW_HEIGHT}`}
            className={fillToneClasses[series[0].tone]}
          />
        ) : null}

        {series.map((entry) => (
          <polyline
            key={entry.name}
            points={toPoints(entry.values, max)}
            fill="none"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
            className={strokeToneClasses[entry.tone]}
          />
        ))}
      </svg>

      <figcaption className="mt-1.5 flex justify-between text-[11px] text-muted-foreground">
        {labels.map((label, index) => (
          <span
            key={`${label}-${index}`}
            className={cn(
              index !== 0 && index !== labels.length - 1 && "hidden sm:inline",
            )}
          >
            {label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
