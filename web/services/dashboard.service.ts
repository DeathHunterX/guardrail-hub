import type { ServiceResult } from "@/types/api";
import type { DashboardOverview } from "@/types/dashboard";

/**
 * Dashboard service. Same contract-first shape as the other services — the
 * exported function is stable; the body is a MOCK TRANSPORT returning
 * representative data until the aggregation endpoint ships on the backend.
 */

const MOCK_LATENCY_MS = 700;

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const hoursAgo = (h: number) =>
  new Date(Date.now() - h * 3_600_000).toISOString();

const mockOverview: DashboardOverview = {
  metrics: [
    {
      id: "projects",
      label: "Total Projects",
      value: "24",
      delta: "+3 this month",
      deltaTone: "success",
    },
    {
      id: "running-operations",
      label: "Running Operations",
      value: "7",
      delta: "2 long-running",
      deltaTone: "default",
    },
    {
      id: "queued-operations",
      label: "Queued Operations",
      value: "12",
      delta: "~4 min wait",
      deltaTone: "default",
    },
    {
      id: "successful-executions",
      label: "Successful Executions",
      value: "1,284",
      delta: "+12% vs last week",
      deltaTone: "success",
    },
    {
      id: "failed-executions",
      label: "Failed Executions",
      value: "23",
      delta: "-8% vs last week",
      deltaTone: "success",
    },
    {
      id: "online-workers",
      label: "Online Workers",
      value: "6/8",
      delta: "2 offline",
      deltaTone: "warning",
    },
    {
      id: "security-findings",
      label: "Security Findings",
      value: "48",
      delta: "5 critical open",
      deltaTone: "destructive",
    },
    {
      id: "performance-tests",
      label: "Performance Tests",
      value: "312",
      delta: "+24 this week",
      deltaTone: "success",
    },
  ],
  charts: {
    operationsTimeline: {
      labels: [
        "Jul 26",
        "Jul 27",
        "Jul 28",
        "Jul 29",
        "Jul 30",
        "Jul 31",
        "Aug 1",
      ],
      series: [
        {
          name: "Succeeded",
          values: [142, 168, 155, 189, 176, 198, 184],
          tone: "primary",
        },
        {
          name: "Failed",
          values: [8, 5, 12, 4, 7, 3, 4],
          tone: "destructive",
        },
      ],
    },
    findingsTrend: {
      labels: [
        "Jul 26",
        "Jul 27",
        "Jul 28",
        "Jul 29",
        "Jul 30",
        "Jul 31",
        "Aug 1",
      ],
      series: [
        {
          name: "Critical",
          values: [9, 8, 8, 7, 6, 5, 5],
          tone: "destructive",
        },
        { name: "High", values: [21, 19, 20, 17, 15, 14, 12], tone: "warning" },
        {
          name: "Medium",
          values: [36, 34, 35, 33, 32, 31, 31],
          tone: "primary",
        },
      ],
    },
    performanceHistory: {
      labels: [
        "Jul 26",
        "Jul 27",
        "Jul 28",
        "Jul 29",
        "Jul 30",
        "Jul 31",
        "Aug 1",
      ],
      series: [
        {
          name: "p95 latency (ms)",
          values: [412, 398, 425, 380, 362, 371, 348],
          tone: "highlight",
        },
      ],
    },
    workerUtilization: [
      { label: "zap-01", value: 82 },
      { label: "zap-02", value: 64 },
      { label: "zap-03", value: 91 },
      { label: "zap-04", value: 0 },
      { label: "jm-01", value: 47 },
      { label: "jm-02", value: 73 },
      { label: "jm-03", value: 55 },
      { label: "jm-04", value: 0 },
    ],
    successRate: {
      centerValue: "98.2%",
      segments: [
        { label: "Succeeded", value: 1284, tone: "success" },
        { label: "Failed", value: 23, tone: "destructive" },
      ],
    },
  },
  operations: [
    {
      id: "op_101",
      name: "Baseline scan",
      project: "api-gateway",
      engine: "ZAP",
      status: "running",
      duration: "12m 04s",
      startedAt: hoursAgo(0.2),
    },
    {
      id: "op_100",
      name: "Load test · checkout",
      project: "checkout-service",
      engine: "JMeter",
      status: "running",
      duration: "4m 51s",
      startedAt: hoursAgo(0.1),
    },
    {
      id: "op_099",
      name: "Full active scan",
      project: "billing-portal",
      engine: "ZAP",
      status: "queued",
      duration: "—",
      startedAt: hoursAgo(0),
    },
    {
      id: "op_098",
      name: "API contract scan",
      project: "partner-api",
      engine: "ZAP",
      status: "succeeded",
      duration: "8m 22s",
      startedAt: hoursAgo(1),
    },
    {
      id: "op_097",
      name: "Soak test · search",
      project: "search-service",
      engine: "JMeter",
      status: "failed",
      duration: "31m 40s",
      startedAt: hoursAgo(3),
    },
    {
      id: "op_096",
      name: "Baseline scan",
      project: "docs-site",
      engine: "ZAP",
      status: "succeeded",
      duration: "2m 18s",
      startedAt: hoursAgo(5),
    },
  ],
  activity: [
    {
      id: "act_01",
      actor: "Guardrail Agent",
      action: "opened remediation PR for",
      target: "CSP header missing · checkout-service",
      at: hoursAgo(0.5),
      tone: "success",
    },
    {
      id: "act_02",
      actor: "Mira Chen",
      action: "triaged finding",
      target: "SQL injection · partner-api",
      at: hoursAgo(2),
      tone: "warning",
    },
    {
      id: "act_03",
      actor: "CI pipeline",
      action: "started scheduled scan on",
      target: "api-gateway",
      at: hoursAgo(4),
      tone: "neutral",
    },
    {
      id: "act_04",
      actor: "Worker pool",
      action: "marked worker offline:",
      target: "zap-worker-04",
      at: hoursAgo(7),
      tone: "destructive",
    },
    {
      id: "act_05",
      actor: "Jonas Weber",
      action: "generated report",
      target: "Security posture · Jul 20–26",
      at: hoursAgo(26),
      tone: "neutral",
    },
  ],
  systemStatus: [
    {
      id: "sys_api",
      name: "Platform API",
      status: "operational",
      detail: "99.99% uptime · 30d",
    },
    {
      id: "sys_workers",
      name: "Worker pool",
      status: "degraded",
      detail: "6 of 8 workers online",
    },
    {
      id: "sys_queue",
      name: "Operation queue",
      status: "operational",
      detail: "12 queued · ~4 min wait",
    },
    {
      id: "sys_notifications",
      name: "Notifications",
      status: "operational",
      detail: "Slack + email delivering",
    },
  ],
  reports: [
    {
      id: "rep_01",
      name: "Security posture · Jul 20–26",
      kind: "Security",
      generatedAt: hoursAgo(26),
    },
    {
      id: "rep_02",
      name: "Checkout load test summary",
      kind: "Performance",
      generatedAt: hoursAgo(50),
    },
    {
      id: "rep_03",
      name: "SOC 2 evidence pack · Q3",
      kind: "Compliance",
      generatedAt: hoursAgo(120),
    },
  ],
};

export async function getDashboardOverview(): Promise<
  ServiceResult<DashboardOverview>
> {
  // Backend integration: GET /dashboard/overview (aggregation endpoint TBD).
  await delay(MOCK_LATENCY_MS);
  return { ok: true, data: mockOverview };
}
