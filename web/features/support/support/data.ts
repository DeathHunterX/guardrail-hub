import {
  CreditCard,
  Plug,
  Rocket,
  ScanSearch,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import type { SupportTopic } from "./types";

/** Copy for the Support page — colocated data module per the content convention. */

export const supportCopy = {
  eyebrow: "Support",
  title: "How can we help?",
  lede: "Answers to the questions we hear most, organized by topic. Can't find yours? The support team reads every email.",
  escalationEmail: "support@guardrailhub.com",
};

export const topics: SupportTopic[] = [
  {
    id: "getting-started",
    icon: Rocket,
    title: "Getting started",
    description: "First scan, first project, first report.",
    faqs: [
      {
        question: "How do I run my first scan?",
        answer:
          "Create a project, add a target you're authorized to test, and ask the agent to run a baseline scan. Results usually land within a few minutes for typical web apps.",
      },
      {
        question: "Which targets am I allowed to scan?",
        answer:
          "Only systems you own or have documented permission to test. The platform verifies target ownership before the first scan — unauthorized scanning violates our Terms of Service.",
      },
      {
        question: "Does Guardrail Hub work with staging environments?",
        answer:
          "Yes, and we recommend it. Point a project at staging first, then promote the same scan configuration to production once you've tuned out the noise.",
      },
    ],
  },
  {
    id: "scans-findings",
    icon: ScanSearch,
    title: "Scans & findings",
    description: "Stuck scans, false positives, severity questions.",
    faqs: [
      {
        question: "My scan has been running for a long time — is it stuck?",
        answer:
          "Large apps can take a while, but the scan view shows per-stage progress. If a stage shows no activity for 15+ minutes, cancel and re-run; failed runs never count against your quota.",
      },
      {
        question: "How do I handle a false positive?",
        answer:
          "Mark the finding as a false positive with a short note. The agent learns the exception for that project and suppresses it in future scans, while keeping it in the audit trail.",
      },
      {
        question: "Why did a finding's severity change between scans?",
        answer:
          "Severity is recalculated per scan using the scanner's score plus context (exposure, authentication state). The finding's history tab shows exactly what changed and why.",
      },
    ],
  },
  {
    id: "account-billing",
    icon: CreditCard,
    title: "Account & billing",
    description: "Plans, invoices, quotas, and cancellation.",
    faqs: [
      {
        question: "How do I upgrade or downgrade my plan?",
        answer:
          "Admins can change plans in Settings → Billing. Upgrades apply immediately with prorated charges; downgrades take effect at the end of the current cycle.",
      },
      {
        question: "Where do I find invoices?",
        answer:
          "Settings → Billing → Invoices lists every invoice as a PDF. Need a specific format or purchase-order reference on invoices? Email us and we'll configure it.",
      },
      {
        question: "What happens when I hit my monthly scan quota?",
        answer:
          "Scans queue instead of failing. You can wait for the next cycle, or an Admin can raise the quota from Billing — the change applies to queued scans immediately.",
      },
    ],
  },
  {
    id: "team-access",
    icon: UserRound,
    title: "Team & access",
    description: "Invites, roles, and permissions.",
    faqs: [
      {
        question: "How do I invite teammates?",
        answer:
          "Settings → Members → Invite. Assign a role at invite time — Developer for day-to-day scanning, Auditor for read-only access. Invites expire after 7 days.",
      },
      {
        question: "What can each role do?",
        answer:
          "Owners and Admins manage everything; Developers run scans and triage findings; Security Leads set policy and approve exceptions; Auditors have read-only access to findings and evidence. The full matrix is on the pricing page.",
      },
      {
        question: "I lost access to my account — what now?",
        answer:
          "Use the password reset first. If your email is no longer accessible or MFA is lost, have a workspace Admin open a recovery request, or email support from your organization's domain.",
      },
    ],
  },
  {
    id: "integrations",
    icon: Plug,
    title: "Integrations & CI/CD",
    description: "Pipelines, PR checks, and issue sync.",
    faqs: [
      {
        question: "How do I add Guardrail Hub to my CI pipeline?",
        answer:
          "Install the CLI in your pipeline, set the project token as a secret, and add the scan step. PR checks post results back automatically. The docs include copy-paste snippets for GitHub Actions and GitLab CI.",
      },
      {
        question: "Jira / Linear sync isn't creating issues — why?",
        answer:
          "Check that the integration user has create-issue permission in the target project and that your sync rules match the finding's severity. The integration log in Settings shows each skipped finding with a reason.",
      },
      {
        question: "Can I export findings to my own tooling?",
        answer:
          "Yes — findings are available as JSON and SARIF via the API on every plan, so you can pipe them into dashboards, SIEMs, or spreadsheets.",
      },
    ],
  },
  {
    id: "security-privacy",
    icon: ShieldCheck,
    title: "Security & privacy",
    description: "Data handling, disclosure, and compliance documents.",
    faqs: [
      {
        question: "Where is my scan data stored and who can see it?",
        answer:
          "Scan data is encrypted at rest, logically isolated per tenant, and visible only to your workspace members per their roles. Details live in the Trust Center.",
      },
      {
        question: "I think I found a vulnerability in Guardrail Hub itself.",
        answer:
          "Thank you — please use the responsible disclosure process at /security rather than regular support. Reports there are acknowledged within 24 hours.",
      },
      {
        question: "How do I get your DPA or audit reports?",
        answer:
          "The DPA is at /dpa and can be executed by emailing legal. SOC 2 reports and questionnaires are available from the Trust Center under NDA.",
      },
    ],
  },
];

export const escalation = {
  title: "Something else? Talk to a person",
  description:
    "For anything not covered here — data recovery, billing disputes, urgent incidents, or just a weird edge case — email the support team directly. A human replies within one business day; scan-blocking issues get priority.",
  emailSubject: "Support request",
};
