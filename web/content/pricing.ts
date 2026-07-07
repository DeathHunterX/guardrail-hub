/**
 * Pricing tier data — shared marketing copy (architecture §12). Lives in
 * content/ because two surfaces render it: the landing pricing section and
 * the dedicated /pricing page. Plan detail specific to the /pricing page
 * stays colocated with that route.
 */

import type { Tier } from "@/types/marketing";

export const pricingCopy = {
  eyebrow: "Pricing",
  title: "Start free. Scale when you're ready.",
  reassurance: "No credit card required · Cancel anytime",
  annualDiscount: 0.8,
} as const;

export const tiers: Tier[] = [
  {
    id: "basic",
    name: "Basic",
    monthly: 0,
    positioning: "For side projects and first scans.",
    features: [
      "1 project",
      "25 agent scans / month",
      "Community scanners (ZAP, Nuclei)",
      "7-day findings history",
      "Community support",
    ],
    cta: { label: "Start Free", href: "/signup" },
  },
  {
    id: "pro",
    name: "Pro",
    monthly: 49,
    positioning: "For teams shipping every week.",
    features: [
      "Unlimited projects",
      "Full scanner suite + custom rules",
      "CI/CD integrations & PR checks",
      "AI remediation suggestions",
      "90-day findings history",
    ],
    cta: { label: "Start Free trial", href: "/signup?plan=pro" },
    featured: true,
  },
  {
    id: "teams",
    name: "Teams",
    monthly: 99,
    positioning: "For orgs standardizing security together.",
    features: [
      "Everything in Pro",
      "Compliance mapping & evidence export",
      "Shared dashboards & RBAC",
      "Jira / Linear sync with SLAs",
      "1-year findings history",
    ],
    cta: { label: "Start Free trial", href: "/signup?plan=teams" },
  },
  {
    id: "enterprise",
    name: "Enterprise",
    monthly: null,
    positioning: "For organizations with auditors on speed dial.",
    features: [
      "SSO / SAML & SCIM",
      "On-prem scan runners",
      "Custom compliance packs",
      "SLAs & dedicated support",
      "Security review & DPA",
    ],
    cta: { label: "Book Demo", href: "/demo" },
  },
];
