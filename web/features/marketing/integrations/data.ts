import type { Integration } from "./types";

export const integrationsCopy = {
  eyebrow: "Integrations",
  title: "Plays conductor to the tools you already trust.",
  lede: "Guardrail Hub orchestrates — it doesn't replace. Your scanners, test suites, pipelines, and workflows stay exactly where they are.",
} as const;

export const categories = [
  { id: "all", label: "All" },
  { id: "scanners", label: "Scanners" },
  { id: "testing", label: "Testing" },
  { id: "cicd", label: "CI/CD" },
  { id: "workflow", label: "Workflow" },
  { id: "cloud", label: "Cloud" },
] as const;

/** Representative, growing toolbelt — not an exhaustive or final roster. */
export const integrations: Integration[] = [
  { name: "OWASP ZAP", description: "Dynamic application security testing", category: "scanners", ring: "inner" },
  { name: "Nuclei", description: "Template-based CVE scanning", category: "scanners", ring: "inner" },
  { name: "Trivy", description: "Container and dependency scanning", category: "scanners", ring: "inner" },
  { name: "Semgrep", description: "Static analysis with custom rules", category: "scanners", ring: "inner" },
  { name: "Gitleaks", description: "Secret detection across history", category: "scanners", ring: "inner" },
  { name: "Checkov", description: "Infrastructure-as-code scanning", category: "scanners", ring: "inner" },
  { name: "Playwright", description: "Browser-driven security E2E flows", category: "testing", ring: "outer" },
  { name: "Selenium", description: "Reuse existing E2E suites for security", category: "testing", ring: "outer" },
  { name: "JMeter", description: "Load and abuse-case testing", category: "testing", ring: "outer" },
  { name: "npm audit", description: "Dependency advisories in every install", category: "testing" },
  { name: "GitHub", description: "Actions, PR checks, code scanning", category: "cicd", ring: "outer" },
  { name: "GitLab", description: "CI pipelines and merge checks", category: "cicd", ring: "outer" },
  { name: "Jenkins", description: "Pipeline steps and gates", category: "cicd", ring: "outer" },
  { name: "Jira", description: "Findings become tracked issues", category: "workflow", ring: "outer" },
  { name: "Linear", description: "Two-way issue sync with SLAs", category: "workflow", ring: "outer" },
  { name: "Slack", description: "Findings and approvals in-channel", category: "workflow", ring: "outer" },
  { name: "AWS", description: "Runner deployment and cloud scans", category: "cloud", ring: "outer" },
  { name: "Vercel", description: "Preview deployment validation", category: "cloud", ring: "outer" },
];
