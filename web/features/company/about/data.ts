import {
  Eye,
  FlaskConical,
  Github,
  Rocket,
  type LucideIcon,
} from "lucide-react";

/** Copy for the About page — colocated data module per the content convention. */

export const aboutCopy = {
  eyebrow: "About us",
  title: "Security validation should feel like shipping, not auditing",
  lede: "Guardrail Hub is built by a small team of security and devtools engineers who believe every team deserves continuous, evidence-backed security — without a dedicated AppSec department.",
};

export const story = {
  heading: "Why we're building this",
  paragraphs: [
    "Most teams meet security twice: once in a pre-launch scramble, and once in an incident postmortem. The tooling in between is fragmented — scanners that speak different formats, compliance checklists that live in spreadsheets, and findings that never make it back into the sprint.",
    "We started Guardrail Hub in 2025 to close that gap with an AI agent that orchestrates the scanners, frameworks, and compliance checks teams already trust — starting with OWASP ZAP — and turns their output into a single, verifiable security posture.",
    "We're early. The platform is in active development and we build in the open: our changelog, roadmap discussions, and MCP server are public. If that resonates, we'd love to have you along.",
  ],
};

export interface CompanyValue {
  icon: LucideIcon;
  title: string;
  description: string;
}

export const values: CompanyValue[] = [
  {
    icon: FlaskConical,
    title: "Evidence over assertion",
    description:
      "A security claim without a scan behind it is marketing. Every posture statement in the product traces back to a real tool execution.",
  },
  {
    icon: Rocket,
    title: "Security at ship speed",
    description:
      "Controls that slow the release train get bypassed. We design for the path developers already take: PRs, pipelines, and chat.",
  },
  {
    icon: Github,
    title: "Open by default",
    description:
      "Our MCP server is open source and our changelog is public. Trust is easier to extend to software you can read.",
  },
  {
    icon: Eye,
    title: "Honest about maturity",
    description:
      "We label what's in development as in development. An early product earns trust by being precise about what works today.",
  },
];

export const stats = [
  { value: "2025", label: "Founded" },
  { value: "100%", label: "Remote team" },
  { value: "3", label: "Public releases" },
  { value: "1", label: "Scanner live, more coming" },
];

export const aboutCta = {
  title: "Help us build it",
  description:
    "We're hiring across engineering and design, and we're always happy to talk to early adopters.",
  primary: { label: "See open roles", href: "/careers" },
  secondary: { label: "Get in touch", href: "/contact" },
};
