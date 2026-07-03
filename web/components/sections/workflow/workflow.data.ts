import {
  Bot,
  Code2,
  Container,
  FileCheck,
  FileCode2,
  FlaskConical,
  Gauge,
  GitPullRequest,
  PackageSearch,
  Plus,
  Radar,
  Scale,
  TestTubes,
  User,
  type LucideIcon,
} from "lucide-react";

export interface WorkflowNode {
  id: string;
  icon: LucideIcon;
  label: string;
  role: string;
  stage: "ask" | "orchestrate" | "scan" | "validate" | "report" | "fix";
}

export const workflowCopy = {
  eyebrow: "How it works",
  title: "One agent. Your entire security pipeline.",
  lede: "You describe the goal. The agent orchestrates your security and testing toolbelt, validates the results, and hands you a signed report with fixes.",
} as const;

export const stages = [
  { id: "ask", label: "Ask", caption: "Tell the agent what to validate — plain language, no config files." },
  { id: "orchestrate", label: "Orchestrate", caption: "The agent picks the right tools for your stack and plans the run." },
  { id: "scan", label: "Scan", caption: "DAST, SAST, dependency and E2E checks run in parallel with shared context." },
  { id: "validate", label: "Validate", caption: "Results are deduplicated and mapped to OWASP, SOC 2, and ISO controls." },
  { id: "report", label: "Report", caption: "A signed, audit-ready report is generated — with every tool's native output attached." },
  { id: "fix", label: "Fix", caption: "Remediation suggestions arrive as reviewable code changes." },
] as const;

/**
 * The scan-stage tools are representative categories, not a fixed roster —
 * the platform's toolbelt (JMeter, Selenium, npm audit, Nuclei, …) keeps
 * growing, which the trailing "+ more" chip communicates.
 */
export const nodes: WorkflowNode[] = [
  { id: "developer", icon: User, label: "Developer", role: '"Validate the release branch"', stage: "ask" },
  { id: "agent", icon: Bot, label: "AI Agent", role: "Plans & orchestrates", stage: "orchestrate" },
  { id: "dast", icon: Radar, label: "OWASP ZAP", role: "DAST", stage: "scan" },
  { id: "sast", icon: Code2, label: "Semgrep", role: "SAST", stage: "scan" },
  { id: "deps", icon: Container, label: "Trivy", role: "Dependencies", stage: "scan" },
  { id: "e2e", icon: FlaskConical, label: "Playwright", role: "Security E2E", stage: "scan" },
  { id: "more", icon: Plus, label: "And more", role: "JMeter · Selenium · npm audit · Nuclei", stage: "scan" },
  { id: "compliance", icon: Scale, label: "Compliance Engine", role: "OWASP · SOC 2 · ISO", stage: "validate" },
  { id: "report", icon: FileCheck, label: "Security Report", role: "87 — Pass", stage: "report" },
  { id: "remediation", icon: GitPullRequest, label: "Remediation", role: "Fix: parameterize query", stage: "fix" },
];

export interface WorkflowOutput {
  id: string;
  icon: LucideIcon;
  label: string;
  role: string;
}

/**
 * Native artifacts attached to every run — each scanner keeps its own
 * report format, so teams never lose the raw output they already read.
 */
export const outputs: WorkflowOutput[] = [
  { id: "zap-html", icon: FileCode2, label: "ZAP HTML", role: "DAST scan report" },
  { id: "allure", icon: TestTubes, label: "Allure Report", role: "Playwright · Selenium" },
  { id: "jmeter-dash", icon: Gauge, label: "JMeter Dashboard", role: "Load & latency stats" },
  { id: "trivy-sbom", icon: PackageSearch, label: "Trivy SBOM", role: "CVEs & licenses" },
];
