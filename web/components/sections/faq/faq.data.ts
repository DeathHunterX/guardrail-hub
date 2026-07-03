export interface FaqItem {
  id: string;
  question: string;
  answer: string;
}

export const faqCopy = {
  eyebrow: "FAQ",
  title: "Questions, answered.",
} as const;

export const faqItems: FaqItem[] = [
  {
    id: "training-data",
    question: "Is my application data used to train AI models?",
    answer:
      "No. Scan data, findings, and code snippets are never used for model training. The agent operates on your data at inference time only, and enterprise plans can pin inference to dedicated infrastructure.",
  },
  {
    id: "production-safety",
    question: "Do scans run against production safely?",
    answer:
      "By default the agent runs read-only, rate-limited checks against production and reserves intrusive tests for staging. Destructive test categories require explicit, logged approval each time.",
  },
  {
    id: "false-positives",
    question: "How do you handle false positives?",
    answer:
      "Findings from all scanners are deduplicated, then the agent verifies exploitability where it safely can and downranks what it can't reproduce. Anything you dismiss teaches your project's baseline.",
  },
  {
    id: "self-hosting",
    question: "Where does scanning infrastructure run? Can we self-host runners?",
    answer:
      "Managed runners run in isolated, single-tenant sandboxes per scan. Enterprise plans can deploy on-prem runners so traffic never leaves your network — the control plane only sees results.",
  },
  {
    id: "tool-selection",
    question: "How does the AI agent decide which tools to run?",
    answer:
      "The agent inspects your stack — routes, dependencies, containers, IaC — and picks scanners whose coverage matches. You can always see the plan before it executes, and pin or exclude tools per project.",
  },
  {
    id: "ci-impact",
    question: "Will this slow down our CI pipeline?",
    answer:
      "PR checks run incrementally on the diff and typically finish in under three minutes. Full scans run asynchronously on schedules or releases, never blocking merges unless you configure a gate.",
  },
  {
    id: "platform-security",
    question: "How is Guardrail Hub itself secured?",
    answer:
      "SOC 2 Type II audited, ISO 27001 certified, single-tenant scan isolation, encryption in transit and at rest, and a public responsible-disclosure program. Details live in our trust center.",
  },
  {
    id: "exports",
    question: "Can we export findings to Jira, Linear, or our SIEM?",
    answer:
      "Yes — native two-way sync for Jira and Linear, webhooks and a typed API for everything else, plus scheduled SARIF/CSV exports for SIEM ingestion.",
  },
];
