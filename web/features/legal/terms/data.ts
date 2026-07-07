import type { LegalDoc } from "@/components/common/legal-article";

/**
 * Terms of Service copy — colocated data module per the content convention.
 * NOTE: placeholder legal text for the pre-launch marketing site; must be
 * reviewed by counsel before general availability.
 */
export const termsDoc: LegalDoc = {
  eyebrow: "Legal",
  title: "Terms of Service",
  lede: "The agreement between you and Guardrail Hub, Inc. governing use of the website, early-access program, and platform.",
  updated: "June 15, 2026",
  sections: [
    {
      id: "agreement",
      heading: "The agreement",
      paragraphs: [
        "These Terms govern access to and use of the Guardrail Hub website, APIs, MCP server, and platform (together, the \"Service\") provided by Guardrail Hub, Inc. By creating an account or using the Service you agree to these Terms on behalf of yourself and, where applicable, the organization you represent.",
        "The Service is currently in active development and offered under an early-access program. Features marked as preview or in development may change or be withdrawn without notice.",
      ],
    },
    {
      id: "accounts",
      heading: "Accounts and acceptable use",
      paragraphs: [
        "You are responsible for your account credentials and for all activity under your account. You agree to use the Service only for lawful purposes and in accordance with these Terms.",
      ],
      items: [
        "Only scan systems you own or are explicitly authorized to test. Running scans against third-party targets without permission is prohibited and may be unlawful.",
        "Do not attempt to disable, bypass, or degrade the Service's security controls, rate limits, or audit logging.",
        "Do not resell or provide the Service to third parties without a written agreement with us.",
        "Do not use the Service to develop a competing product by systematically extracting its output.",
      ],
    },
    {
      id: "authorization-to-scan",
      heading: "Authorization to scan",
      paragraphs: [
        "Security scanning can disrupt target systems. By initiating a scan you represent that you have documented authorization to test every target you configure, and you accept responsibility for scan traffic the Service generates on your instructions. We may suspend scans that appear to target systems without authorization.",
      ],
    },
    {
      id: "customer-content",
      heading: "Your content and our IP",
      paragraphs: [
        "You retain all rights to the code, configurations, and scan targets you submit and to the reports generated from them (\"Customer Content\"). You grant us a limited license to process Customer Content solely to provide the Service.",
        "We retain all rights to the Service itself, including software, models, documentation, and branding. Open-source components, including our MCP server, are licensed under their respective open-source licenses.",
      ],
    },
    {
      id: "early-access",
      heading: "Early access and service levels",
      paragraphs: [
        "During early access the Service is provided without uptime commitments or support SLAs. We publish live availability on our status page and document known limitations in the changelog. Paid plans introduced at general availability will carry their own service terms.",
      ],
    },
    {
      id: "fees",
      heading: "Fees",
      paragraphs: [
        "Early-access use is free of charge unless otherwise agreed in writing. When paid plans launch, pricing will be published on the website, charges will recur per the plan's billing cycle, and taxes are your responsibility unless we are required to collect them.",
      ],
    },
    {
      id: "disclaimers",
      heading: "Disclaimers",
      paragraphs: [
        "The Service assists your security program; it does not replace it. Scan results reflect what the configured tools detected at the time of execution — no scanner finds every vulnerability, and a passing result is not a guarantee that a system is secure. The Service is provided \"as is\" without warranties of any kind, express or implied, to the maximum extent permitted by law.",
      ],
    },
    {
      id: "liability",
      heading: "Limitation of liability",
      paragraphs: [
        "To the maximum extent permitted by law, neither party is liable for indirect, incidental, special, or consequential damages, and our aggregate liability under these Terms is capped at the greater of USD 100 or the amounts you paid us in the twelve months before the claim. Nothing in these Terms limits liability that cannot be limited by law.",
      ],
    },
    {
      id: "termination",
      heading: "Suspension and termination",
      paragraphs: [
        "You may stop using the Service and delete your account at any time. We may suspend or terminate access for material breach of these Terms, including unauthorized scanning, with notice where practicable. Upon termination we delete Customer Content per the retention terms in our Privacy Policy and DPA.",
      ],
    },
    {
      id: "general",
      heading: "Governing law and changes",
      paragraphs: [
        "These Terms are governed by the laws of the State of California, excluding its conflict-of-law rules, and disputes are resolved in the state or federal courts of San Francisco County. We may update these Terms; material changes will be announced by email at least 14 days in advance. Continued use after the effective date constitutes acceptance.",
        "Questions about these Terms: legal@guardrailhub.com.",
      ],
    },
  ],
};
