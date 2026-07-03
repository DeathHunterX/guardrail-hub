import {
  Bot,
  ClipboardCheck,
  Code2,
  Gauge,
  Plug,
  ShieldCheck,
  Sparkles,
  TestTubeDiagonal,
  type LucideIcon,
} from "lucide-react";

import { siteConfig } from "@/config/site";

/**
 * Chrome-level copy and navigation data (architecture §12: colocated data
 * modules are the CMS). Section-specific copy lives in each section's
 * *.data.ts — this file owns only the header, announcement, and footer.
 */

export interface NavLink {
  label: string;
  href: string;
  external?: boolean;
}

export interface NavMegaItem extends NavLink {
  description: string;
  icon: LucideIcon;
}

export interface NavGroup {
  label: string;
  items: NavMegaItem[];
}

export interface Navigation {
  groups: NavGroup[];
  links: NavLink[];
}

export const navigation: Navigation = {
  groups: [
    {
      label: "Product",
      items: [
        {
          label: "Features",
          href: "#features",
          description: "Everything the platform does, at a glance.",
          icon: Sparkles,
        },
        {
          label: "AI Agents",
          href: "#agent",
          description: "Conversational security validation on demand.",
          icon: Bot,
        },
        {
          label: "Dashboard",
          href: "#showcase",
          description: "A security command center that runs itself.",
          icon: Gauge,
        },
        {
          label: "Integrations",
          href: "#integrations",
          description: "ZAP, Nuclei, Trivy, Semgrep, CI/CD, and more.",
          icon: Plug,
        },
      ],
    },
    {
      // Role pages ship post-launch; each role currently deep-links to the
      // landing section that answers that persona's first question.
      label: "Solutions",
      items: [
        {
          label: "Developers",
          href: "#features",
          description: "Security checks that live where you ship.",
          icon: Code2,
        },
        {
          label: "QA Engineers",
          href: "#agent",
          description: "Describe the test — the agent runs the suite.",
          icon: TestTubeDiagonal,
        },
        {
          label: "DevSecOps",
          href: "#compliance",
          description: "Continuous controls, audit-ready evidence.",
          icon: ShieldCheck,
        },
        {
          label: "Enterprise",
          href: "#pricing",
          description: "SSO, on-prem runners, custom compliance packs.",
          icon: ClipboardCheck,
        },
      ],
    },
  ],
  links: [
    { label: "Pricing", href: "#pricing" },
    { label: "Docs", href: siteConfig.links.docs, external: true },
    {
      label: "Changelog",
      href: `${siteConfig.links.github}/releases`,
      external: true,
    },
  ],
};

export interface Announcement {
  /** Bump the id to re-show the bar to users who dismissed a previous one. */
  id: string;
  message: string;
  shortMessage: string;
  linkLabel: string;
  href: string;
}

export const announcement: Announcement = {
  id: "agents-2-0",
  message: "Introducing Guardrail Agents 2.0 — autonomous remediation PRs.",
  shortMessage: "Guardrail Agents 2.0 is here.",
  linkLabel: "Read the announcement",
  href: `${siteConfig.links.github}/releases`,
};
