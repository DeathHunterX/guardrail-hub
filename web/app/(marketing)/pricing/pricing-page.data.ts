/**
 * Copy for the dedicated /pricing page — colocated data module per the
 * content convention. Tier names, prices, and feature lists are shared with
 * the landing section via features/marketing/pricing/data.ts; this
 * file adds the detail the landing section intentionally leaves out:
 * audience, seat roles, and the benefits of committing to each plan.
 */

export const pricingPageCopy = {
  eyebrow: "Pricing",
  title: "Plans, roles, and what you get with each",
  lede: "Every plan runs the same AI agent and scanners. Higher tiers add seats, roles, compliance evidence, and the controls larger teams need. Annual billing saves 20% on every paid plan.",
  reassurance: "No credit card required · Cancel anytime · Prices in USD, per month",
};

export interface TierDetail {
  /** Matches Tier.id from the landing pricing data. */
  tierId: string;
  audience: string;
  /** Seat roles unlocked by the plan. */
  roles: { name: string; description: string }[];
  seats: string;
  /** Outcome-level benefits of subscribing — the "why", not the feature diff. */
  benefits: string[];
}

export const tierDetails: TierDetail[] = [
  {
    tierId: "basic",
    audience: "Solo developers validating a side project or trying the platform.",
    seats: "1 seat",
    roles: [
      {
        name: "Owner",
        description: "Full control of the project, scans, and findings.",
      },
    ],
    benefits: [
      "Ship a first security baseline in an afternoon — no procurement, no card.",
      "Learn the agent workflow before putting money on it.",
      "Findings in the same normalized format paid plans use, so upgrading keeps your history conventions.",
    ],
  },
  {
    tierId: "pro",
    audience: "Product teams shipping weekly that want security in the PR loop.",
    seats: "Up to 10 seats",
    roles: [
      {
        name: "Admin",
        description: "Manages members, projects, integrations, and billing.",
      },
      {
        name: "Developer",
        description: "Runs scans, triages findings, and applies AI remediation.",
      },
    ],
    benefits: [
      "Findings arrive as PR checks — vulnerabilities get fixed before merge, not after release.",
      "AI remediation suggestions cut mean-time-to-fix from days to hours.",
      "90-day history turns one-off scans into a trend you can show your lead.",
    ],
  },
  {
    tierId: "teams",
    audience: "Organizations standardizing security across several squads.",
    seats: "Up to 50 seats",
    roles: [
      {
        name: "Admin",
        description: "Manages members, projects, integrations, and billing.",
      },
      {
        name: "Developer",
        description: "Runs scans, triages findings, and applies AI remediation.",
      },
      {
        name: "Security Lead",
        description: "Sets policies, approves exceptions, owns the posture dashboard.",
      },
      {
        name: "Auditor",
        description: "Read-only access to findings and compliance evidence exports.",
      },
    ],
    benefits: [
      "One shared dashboard replaces per-squad spreadsheets — posture is visible org-wide.",
      "Compliance mapping generates SOC 2 / ISO 27001 evidence as a by-product of scanning.",
      "RBAC keeps auditors read-only and developers scoped to their own projects.",
      "Jira / Linear sync with SLAs makes findings someone's job, not everyone's guilt.",
    ],
  },
  {
    tierId: "enterprise",
    audience: "Regulated organizations with auditors, procurement, and an SSO mandate.",
    seats: "Unlimited seats",
    roles: [
      {
        name: "Custom roles",
        description: "Role definitions mapped from your IdP via SSO/SAML and SCIM.",
      },
      {
        name: "All Teams roles",
        description: "Admin, Developer, Security Lead, and Auditor included as defaults.",
      },
    ],
    benefits: [
      "On-prem scan runners keep scan traffic and findings inside your network boundary.",
      "Custom compliance packs match your framework, not the other way around.",
      "A named support engineer and SLAs — answers in hours, contractually.",
      "Security review, DPA, and questionnaire support for procurement, handled by us.",
    ],
  },
];

export interface ComparisonRow {
  capability: string;
  /** Values keyed in tier order: basic, pro, teams, enterprise. */
  values: [string, string, string, string];
}

export const comparisonRows: ComparisonRow[] = [
  { capability: "Projects", values: ["1", "Unlimited", "Unlimited", "Unlimited"] },
  { capability: "Agent scans / month", values: ["25", "Unlimited", "Unlimited", "Unlimited"] },
  { capability: "Seats", values: ["1", "10", "50", "Unlimited"] },
  { capability: "Scanner suite", values: ["ZAP, Nuclei", "Full + custom rules", "Full + custom rules", "Full + on-prem runners"] },
  { capability: "CI/CD & PR checks", values: ["—", "Included", "Included", "Included"] },
  { capability: "AI remediation suggestions", values: ["—", "Included", "Included", "Included"] },
  { capability: "Findings history", values: ["7 days", "90 days", "1 year", "Custom"] },
  { capability: "Compliance mapping & evidence export", values: ["—", "—", "Included", "Custom packs"] },
  { capability: "Shared dashboards & RBAC", values: ["—", "—", "Included", "Included"] },
  { capability: "Jira / Linear sync with SLAs", values: ["—", "—", "Included", "Included"] },
  { capability: "SSO / SAML & SCIM", values: ["—", "—", "—", "Included"] },
  { capability: "Support", values: ["Community", "Standard", "Priority", "Dedicated + SLA"] },
];

export const pricingFaq = [
  {
    question: "How does the free plan differ from a trial?",
    answer:
      "Basic is free forever, not a timer. Paid plans start with a free trial on top — you only pick a plan when the limits stop fitting.",
  },
  {
    question: "What happens to my data if I downgrade?",
    answer:
      "Nothing is deleted immediately. Findings older than the new plan's history window become read-only for 30 days so you can export them, then age out.",
  },
  {
    question: "Can I switch between monthly and annual billing?",
    answer:
      "Yes — switching to annual applies the 20% discount at the next cycle; switching to monthly takes effect when the annual period ends.",
  },
  {
    question: "Do agent scans count against my quota if they fail?",
    answer:
      "No. Only completed scans count. Failed or cancelled runs are logged for debugging but never billed against the monthly quota.",
  },
  {
    question: "The product is in development — will prices change?",
    answer:
      "Early-access pricing is locked for 12 months from your subscription date. If list prices change, you keep your rate for that period.",
  },
];

export const pricingCta = {
  title: "Not sure which plan fits?",
  description:
    "Tell us your team size and stack — we'll recommend a plan in one email, or walk you through it on a demo.",
  primary: { label: "Book a demo", href: "/demo" },
  secondary: { label: "Ask support", href: "/support" },
};
