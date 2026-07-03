import {
  Bot,
  ClipboardCheck,
  FileBarChart,
  History,
  KeyRound,
  Layers,
  RefreshCw,
  Sparkles,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export interface Feature {
  icon: LucideIcon;
  title: string;
  description: string;
  size: "hero" | "wide" | "tall" | "standard";
  visual:
    | "chat"
    | "commits"
    | "dedupe"
    | "checklist"
    | "diff"
    | "pipeline"
    | "report"
    | "team"
    | "secrets"
    | "audit";
}

export const featuresCopy = {
  eyebrow: "The platform",
  title: "Everything security validation needs. Nothing you have to babysit.",
  lede: "Each capability is one conversation away — and every persona finds theirs.",
} as const;

export const features: Feature[] = [
  {
    icon: Bot,
    title: "Conversational security agent",
    description:
      "Describe intent in plain language; the agent plans, runs, and explains the entire validation.",
    size: "hero",
    visual: "chat",
  },
  {
    icon: RefreshCw,
    title: "Continuous validation",
    description: "Every push, every PR, every schedule.",
    size: "standard",
    visual: "commits",
  },
  {
    icon: Layers,
    title: "Unified findings",
    description: "Deduplicated across all scanners, ranked by real risk.",
    size: "standard",
    visual: "dedupe",
  },
  {
    icon: ClipboardCheck,
    title: "Compliance mapping",
    description:
      "Findings auto-mapped to OWASP, SOC 2, ISO 27001, and PCI DSS controls.",
    size: "tall",
    visual: "checklist",
  },
  {
    icon: Sparkles,
    title: "AI remediation",
    description: "Fix suggestions arrive as reviewable code diffs.",
    size: "standard",
    visual: "diff",
  },
  {
    icon: Workflow,
    title: "CI/CD native",
    description: "GitHub Actions, GitLab CI, Jenkins — first-class.",
    size: "standard",
    visual: "pipeline",
  },
  {
    icon: FileBarChart,
    title: "Executive reporting",
    description:
      "Shareable, branded, audit-ready reports your leadership actually reads.",
    size: "wide",
    visual: "report",
  },
  {
    icon: Users,
    title: "Team workflows",
    description: "Assignments, SLAs, and Jira/Linear sync built in.",
    size: "standard",
    visual: "team",
  },
  {
    icon: KeyRound,
    title: "Secrets detection",
    description:
      "Gitleaks-powered history sweeps catch keys and tokens before they ship.",
    size: "standard",
    visual: "secrets",
  },
  {
    icon: History,
    title: "Immutable audit trail",
    description:
      "Every agent action is logged, timestamped, and exportable for auditors.",
    size: "standard",
    visual: "audit",
  },
];

export const demoPrompts = [
  "Scan the payment flow for auth issues",
  "Are we exposed to CVE-2026-1337?",
  "Prep SOC 2 evidence for Q3",
] as const;
