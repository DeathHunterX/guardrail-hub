import type { ChartDatum, ChartSeries, DonutSegment } from "@/types/charts";

/** Dashboard overview contracts — shared by the dashboard service and feature. */

export type MetricTone = "default" | "success" | "warning" | "destructive";

export type DashboardMetricId =
  | "projects"
  | "running-operations"
  | "queued-operations"
  | "successful-executions"
  | "failed-executions"
  | "online-workers"
  | "security-findings"
  | "performance-tests";

export interface DashboardMetric {
  id: DashboardMetricId;
  label: string;
  /** Preformatted display value, e.g. "1,284" or "98.2%". */
  value: string;
  /** Preformatted trend line, e.g. "+12% vs last week". */
  delta: string;
  deltaTone: MetricTone;
}

export type OperationStatus = "running" | "queued" | "succeeded" | "failed";

export interface OperationRow {
  id: string;
  name: string;
  project: string;
  engine: string;
  status: OperationStatus;
  /** Preformatted duration, e.g. "4m 12s"; em dash while queued. */
  duration: string;
  /** ISO timestamp. */
  startedAt: string;
}

export interface ActivityEvent {
  id: string;
  actor: string;
  action: string;
  target: string;
  /** ISO timestamp. */
  at: string;
  tone: "success" | "warning" | "destructive" | "neutral";
}

export interface SystemComponentStatus {
  id: string;
  name: string;
  status: "operational" | "degraded" | "outage";
  detail: string;
}

export interface ReportSummary {
  id: string;
  name: string;
  kind: "Security" | "Performance" | "Compliance";
  /** ISO timestamp. */
  generatedAt: string;
}

export interface TimeSeriesChart {
  labels: string[];
  series: ChartSeries[];
}

export interface DashboardCharts {
  operationsTimeline: TimeSeriesChart;
  findingsTrend: TimeSeriesChart;
  performanceHistory: TimeSeriesChart;
  workerUtilization: ChartDatum[];
  successRate: {
    centerValue: string;
    segments: DonutSegment[];
  };
}

export interface DashboardOverview {
  metrics: DashboardMetric[];
  charts: DashboardCharts;
  operations: OperationRow[];
  activity: ActivityEvent[];
  systemStatus: SystemComponentStatus[];
  reports: ReportSummary[];
}
