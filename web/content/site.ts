import {
  Bot,
  ClipboardCheck,
  Code2,
  Gauge,
  Plug,
  ShieldCheck,
  Sparkles,
  TestTubeDiagonal,
} from "lucide-react";

import { externalLinks } from "@/constants/external-links";
import type { Announcement, Navigation } from "@/types/navigation";

/**
 * Chrome-level copy and navigation data (architecture §12: colocated data
 * modules are the CMS). Section-specific copy lives in each section's
 * *.data.ts — this file owns only the header, announcement, and footer.
 */

export const navigation: Navigation = {
  groups: [
    {
      label: "Product",
      items: [
        {
          // "/#" anchors resolve from any route: they navigate home first
          // when needed, then scroll to the section.
          label: "Features",
          href: "/#features",
          description: "Everything the platform does, at a glance.",
          icon: Sparkles,
        },
        {
          label: "AI Agents",
          href: "/#agent",
          description: "Conversational security validation on demand.",
          icon: Bot,
        },
        {
          label: "Dashboard",
          href: "/#showcase",
          description: "A security command center that runs itself.",
          icon: Gauge,
        },
        {
          label: "Integrations",
          href: "/#integrations",
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
          href: "/#features",
          description: "Security checks that live where you ship.",
          icon: Code2,
        },
        {
          label: "QA Engineers",
          href: "/#agent",
          description: "Describe the test — the agent runs the suite.",
          icon: TestTubeDiagonal,
        },
        {
          label: "DevSecOps",
          href: "/#compliance",
          description: "Continuous controls, audit-ready evidence.",
          icon: ShieldCheck,
        },
        {
          label: "Enterprise",
          href: "/pricing",
          description: "SSO, on-prem runners, custom compliance packs.",
          icon: ClipboardCheck,
        },
      ],
    },
  ],
  links: [
    // On the landing page Pricing scrolls to the section; everywhere else it
    // opens the dedicated /pricing page with plan, role, and benefit details.
    { label: "Pricing", href: "/pricing", landingHref: "#pricing" },
    { label: "Docs", href: externalLinks.docs, external: true },
    { label: "Changelog", href: "/changelog" },
  ],
};

export const announcement: Announcement = {
  id: "agents-2-0",
  message: "Introducing Guardrail Agents 2.0 — autonomous remediation PRs.",
  shortMessage: "Guardrail Agents 2.0 is here.",
  linkLabel: "Read the announcement",
  href: `${externalLinks.github}/releases`,
};
