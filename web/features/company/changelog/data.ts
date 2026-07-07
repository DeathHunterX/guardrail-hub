import { externalLinks } from "@/constants/external-links";

import type { Release } from "./types";

/** Copy for the Changelog page — colocated data module per the content convention. */

export const changelogCopy = {
  eyebrow: "Changelog",
  title: "What's new in Guardrail Hub",
  lede: "Every release, in the open — what shipped, what changed, and what's next. Full technical notes live with each GitHub release.",
};

/** Builds the GitHub release-notes URL for a version tag. */
const releaseUrl = (tag: string) =>
  `${externalLinks.github}/releases/tag/${tag}`;

export const releases: Release[] = [
  {
    version: "v0.3.0",
    date: "June 24, 2026",
    stage: "In development",
    title: "Compliance mapping preview & a smarter agent",
    overview:
      "This release connects scan output to compliance evidence for the first time: findings from ZAP scans can now be mapped to SOC 2 and ISO 27001 controls, and the agent explains each mapping instead of just asserting it. The marketing site also went live, giving the project a public home ahead of early access.",
    highlights: [
      {
        kind: "New",
        text: "Compliance mapping preview — scan findings link to SOC 2 / ISO 27001 controls with an evidence trail.",
      },
      {
        kind: "New",
        text: "Public marketing site with product tour, pricing preview, and this changelog.",
      },
      {
        kind: "Improved",
        text: "Agent explanations now cite the exact scan output behind every posture statement.",
      },
      {
        kind: "Fixed",
        text: "Scan sessions no longer stall when ZAP's spider finishes before the passive scan queue drains.",
      },
    ],
    detailUrl: releaseUrl("v0.3.0"),
    latest: true,
  },
  {
    version: "v0.2.0",
    date: "May 12, 2026",
    stage: "In development",
    title: "AI agent orchestration & signed reports",
    overview:
      "The AI agent moved from proof-of-concept to a real orchestration layer: it plans multi-step scans, retries flaky stages, and produces a signed report at the end. Authentication landed across the MCP server, so every tool call is now attributable to a user and logged.",
    highlights: [
      {
        kind: "New",
        text: "Agent-orchestrated scan plans — spider, baseline, and active stages sequenced and monitored automatically.",
      },
      {
        kind: "New",
        text: "Token-based authentication and per-call audit logging across all MCP tools.",
      },
      {
        kind: "New",
        text: "Signed PDF/JSON scan reports with a verifiable checksum.",
      },
      {
        kind: "Improved",
        text: "Scan status streaming — long-running scans report progress instead of blocking until completion.",
      },
    ],
    detailUrl: releaseUrl("v0.2.0"),
  },
  {
    version: "v0.1.0",
    date: "March 30, 2026",
    stage: "In development",
    title: "First public preview — ZAP scanning over MCP",
    overview:
      "The first public build of Guardrail Hub: an open-source MCP server that exposes OWASP ZAP to AI agents. It covers the core loop — configure a target, run a baseline scan, and read structured findings back — and set the foundation every later release builds on.",
    highlights: [
      {
        kind: "New",
        text: "Open-source MCP server exposing OWASP ZAP baseline scans as agent-callable tools.",
      },
      {
        kind: "New",
        text: "Structured findings API — normalized severity, evidence, and remediation fields per alert.",
      },
      {
        kind: "New",
        text: "Target authorization checks — scans refuse to start against unverified hosts.",
      },
    ],
    detailUrl: releaseUrl("v0.1.0"),
  },
];

export const changelogCta = {
  title: "Follow the roadmap",
  description:
    "Release candidates, RFCs, and roadmap discussions all happen on GitHub. Watch the repo to get notified the moment a release ships.",
  action: { label: "View releases on GitHub", href: `${externalLinks.github}/releases` },
};
