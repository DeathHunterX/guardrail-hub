/** Hero copy and demo script (spec §3). */

export const heroCopy = {
  eyebrow: "AI-native security validation",
  headline: { lead: "Ship secure software.", highlight: "Let the AI prove it." },
  description:
    "Guardrail Hub orchestrates scanners, frameworks, and compliance checks through a single AI agent — from first scan to signed report, without the tool sprawl.",
  trust: ["No agents to install", "SOC 2 Type II", "5-minute setup"],
} as const;

export const demoScript = {
  userMessage: "Run a full security validation on api.acme.dev",
  agentReply:
    "Starting a full validation. I'll crawl the API surface, run DAST and dependency checks, then map findings to your compliance frameworks.",
  tools: ["ZAP", "Nuclei", "Trivy", "Semgrep"],
  logs: [
    "Crawling routes… 214 endpoints found",
    "Testing auth flows on /api/v1/*",
    "nuclei: 3,120 templates queued",
    "trivy: scanning 42 dependencies",
    "semgrep: 87 rules matched context",
  ],
  score: 87,
  findings: [
    { severity: "destructive", title: "SQL Injection", asset: "/api/v1/users", tag: "Critical" },
    { severity: "warning", title: "Missing rate limit", asset: "/api/v1/auth", tag: "Medium" },
    { severity: "warning", title: "Outdated lodash 4.17.19", asset: "package.json", tag: "Medium" },
  ],
} as const;

export type DemoFinding = (typeof demoScript.findings)[number];
