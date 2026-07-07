export const showcaseCopy = {
  eyebrow: "The dashboard",
  title: "A security command center that runs itself.",
  lede: "Score, findings, compliance, and agent activity — live in one place, for the whole team.",
} as const;

export const dashboard = {
  score: 87,
  scoreDelta: "+5 this week",
  trend: [42, 38, 35, 36, 30, 28, 24, 25, 19, 16, 14, 11],
  compliance: [
    { framework: "OWASP Top 10", value: 90, label: "9/10" },
    { framework: "SOC 2", value: 94, label: "94%" },
    { framework: "ISO 27001", value: 91, label: "91%" },
  ],
  findings: [
    { severity: "destructive", title: "SQL Injection", asset: "/api/v1/users", scanner: "ZAP", status: "Open", assignee: "AL" },
    { severity: "destructive", title: "Exposed API key", asset: "payments-svc", scanner: "Semgrep", status: "Triaged", assignee: "MK" },
    { severity: "warning", title: "Missing rate limit", asset: "/api/v1/auth", scanner: "ZAP", status: "Triaged", assignee: "TS" },
    { severity: "warning", title: "lodash 4.17.19 CVE", asset: "package.json", scanner: "Trivy", status: "Fixed", assignee: "AL" },
    { severity: "neutral", title: "Verbose error pages", asset: "/admin", scanner: "Nuclei", status: "Open", assignee: "MK" },
  ],
  recommendations: [
    { title: "Rotate exposed API key", detail: "Found in 2 repos — payments-svc, billing-worker" },
    { title: "Parameterize user query", detail: "Fix ready for review · 3 files" },
  ],
  timeline: [
    { stage: "Queued", width: 8 },
    { stage: "Crawling", width: 22 },
    { stage: "Scanning", width: 38 },
    { stage: "Analyzing", width: 20 },
    { stage: "Reporting", width: 12 },
  ],
  logs: [
    "[12:04:11] zap: spider completed — 214 routes",
    "[12:04:19] nuclei: template pack cve-2026 loaded",
    "[12:04:33] trivy: 42 dependencies scanned, 1 medium",
    "[12:04:41] semgrep: taint analysis on payments-svc",
    "[12:04:58] agent: deduplicating 23 raw findings → 5",
    "[12:05:02] compliance: SOC 2 CC7.1 evidence attached",
    "[12:05:09] report: draft generated (rev 4)",
  ],
} as const;

export type DashboardFinding = (typeof dashboard.findings)[number];

export const showcaseTabs = [
  { id: "overview", label: "Overview" },
  { id: "findings", label: "Findings" },
  { id: "compliance", label: "Compliance" },
  { id: "activity", label: "Agent Activity" },
] as const;
