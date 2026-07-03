export const complianceCopy = {
  eyebrow: "Compliance",
  title: "Audit-ready, every day of the year.",
  lede: "Every finding is mapped to the frameworks you answer to — evidence collected as a side effect of scanning, not a quarterly scramble.",
  bullets: [
    "Findings auto-mapped to OWASP, SOC 2, ISO 27001, and PCI DSS controls",
    "One-click evidence export with timestamps and attestations",
    "Continuous control monitoring between audits",
  ],
} as const;

export interface ControlRow {
  control: string;
  evidence: string;
  status: "passing" | "attention";
  validated: string;
}

export const controls: ControlRow[] = [
  { control: "OWASP A03: Injection", evidence: "214 scan runs", status: "passing", validated: "4 min ago" },
  { control: "SOC 2 CC7.1", evidence: "Monitoring config", status: "passing", validated: "4 min ago" },
  { control: "SOC 2 CC6.1", evidence: "Access review log", status: "passing", validated: "1 h ago" },
  { control: "ISO 27001 A.12.6", evidence: "Patch cadence report", status: "passing", validated: "1 h ago" },
  { control: "PCI DSS 6.5.1", evidence: "2 open findings", status: "attention", validated: "4 min ago" },
];

export const certifications = [
  { name: "SOC 2 Type II", detail: "Audited annually" },
  { name: "ISO 27001", detail: "Certified" },
  { name: "GDPR", detail: "EU data residency" },
] as const;

export const coverage = "Coverage: OWASP Top 10 — 9/10 · SOC 2 — 94% · updated 4 min ago";
