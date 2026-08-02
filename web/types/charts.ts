/** Shared chart contracts — consumed by chart components and feature data. */

export type ChartTone =
  "primary" | "highlight" | "success" | "warning" | "destructive";

export interface ChartSeries {
  name: string;
  values: number[];
  tone: ChartTone;
}

export interface ChartDatum {
  label: string;
  value: number;
}

export interface DonutSegment {
  label: string;
  value: number;
  tone: ChartTone;
}
