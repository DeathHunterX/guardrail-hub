import { Blocks, FileWarning, FolderSearch, Wrench } from "lucide-react";

import type { Pain } from "./types";

export const problemCopy = {
  eyebrow: "The problem",
  title: "Security testing wasn't built for how you ship.",
  lede: "Modern teams deploy daily. Their security stack still assumes quarterly audits.",
} as const;

/**
 * Copy is written for instant recognition, not description: each card should
 * make a reader think "that's literally our pipeline", not "I see".
 */
export const pains: Pain[] = [
  {
    icon: Blocks,
    title: "Every scanner speaks a different language",
    description:
      "ZAP, Nuclei, Trivy, Semgrep — no shared history, no shared ownership, no shared decisions.",
    vignette: "sprawl",
  },
  {
    icon: Wrench,
    title: "Glue code holds it all together",
    description:
      "Every scan is a relay of exports, converters, and scripts someone has to babysit at 2am.",
    vignette: "gluecode",
  },
  {
    icon: FileWarning,
    title: "1,847 alerts. Zero answers.",
    description:
      "Unranked, unowned, unassigned — a wall of findings is the same as none.",
    vignette: "findings",
  },
  {
    icon: FolderSearch,
    title: "Audit evidence is an excavation",
    description:
      "Proof lives in screenshots, Slack threads, and someone's inbox — and the audit starts in 14 days.",
    vignette: "audit",
  },
];

/** The hand-rolled relay every team recognizes as their own pipeline. */
export const glueSteps = [
  "Run ZAP",
  "Export JSON",
  "Convert",
  "Run Semgrep",
  "Merge",
  "Upload SIEM",
  "Notify Slack",
] as const;

/** Severity distribution for the alert-fatigue dashboard vignette. */
export const severityRows = [
  { label: "Critical", count: 48, tone: "destructive" },
  { label: "High", count: 296, tone: "warning" },
  { label: "Medium", count: 803, tone: "warning-soft" },
  { label: "Low", count: 700, tone: "neutral" },
] as const;

/** Where audit evidence actually lives today. */
export const evidenceScatter = [
  "Screenshot",
  "Slack",
  "Email",
  "PDF",
  "Confluence",
  "???",
] as const;

/** Narrative metric chain: each number leads into the next. */
export const statusQuoChain = [
  "4 tools",
  "0 shared context",
  "1,847 alerts",
  "14 days lost",
] as const;

/** Emotional closer before the hand-off to the solution section. */
export const problemClosing = {
  statement: "Your security stack keeps growing.",
  counter: "Your confidence doesn't.",
  cta: "See how one agent replaces this entire workflow",
} as const;
