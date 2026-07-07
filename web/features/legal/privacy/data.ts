import type { LegalDoc } from "@/components/common/legal-article";

/**
 * Privacy Policy copy — colocated data module per the content convention.
 * NOTE: placeholder legal text for the pre-launch marketing site; must be
 * reviewed by counsel before general availability.
 */
export const privacyDoc: LegalDoc = {
  eyebrow: "Legal",
  title: "Privacy Policy",
  lede: "How Guardrail Hub, Inc. collects, uses, and protects personal data across our website and platform.",
  updated: "June 15, 2026",
  sections: [
    {
      id: "scope",
      heading: "Who this policy covers",
      paragraphs: [
        "This policy applies to visitors of guardrailhub.com, participants in our early-access program, and users of the Guardrail Hub platform. It covers personal data we handle as a controller — account details, communications, and website analytics.",
        "Data your organization submits to the platform for scanning (repositories, target URLs, scan output) is processed on your organization's instructions under our Data Processing Addendum, where we act as a processor.",
      ],
    },
    {
      id: "data-we-collect",
      heading: "Data we collect",
      paragraphs: ["We collect only what we need to operate the service:"],
      items: [
        "Account data — name, work email, organization name, and authentication identifiers when you sign up or book a demo.",
        "Usage data — pages visited, features used, and approximate location derived from IP address, collected via privacy-respecting analytics.",
        "Communications — emails, support requests, and community messages you send us.",
        "Scan metadata — timestamps, target identifiers, and result summaries needed to render your dashboard and reports.",
      ],
    },
    {
      id: "how-we-use-data",
      heading: "How we use data",
      paragraphs: [
        "We use personal data to provide and secure the service, respond to requests, send product updates you have opted into, and understand aggregate usage so we can improve the product. We do not sell personal data, and we do not use customer scan content to train shared machine-learning models.",
      ],
    },
    {
      id: "legal-bases",
      heading: "Legal bases (GDPR)",
      paragraphs: [
        "Where the GDPR applies, we rely on: performance of a contract (operating your account), legitimate interests (securing the service, product analytics), consent (marketing communications), and legal obligations (tax and accounting records). You may withdraw consent at any time.",
      ],
    },
    {
      id: "sharing",
      heading: "Sharing and subprocessors",
      paragraphs: [
        "We share personal data only with service providers who help us run Guardrail Hub — cloud hosting, email delivery, analytics, and payment processing — under contracts that limit their use of the data to our instructions. The current subprocessor list is published in our Trust Center.",
      ],
    },
    {
      id: "retention",
      heading: "Retention",
      paragraphs: [
        "Account data is retained while your account is active and deleted or anonymized within 90 days of account closure. Scan results follow your organization's configured retention window. Backups age out on a rolling 35-day schedule.",
      ],
    },
    {
      id: "security",
      heading: "Security",
      paragraphs: [
        "Personal data is encrypted in transit (TLS 1.2+) and at rest (AES-256). Access is role-based, logged, and reviewed. Our own platform scans our infrastructure continuously — we run Guardrail Hub on Guardrail Hub.",
      ],
    },
    {
      id: "your-rights",
      heading: "Your rights",
      paragraphs: [
        "Depending on your jurisdiction, you may have the right to access, correct, export, restrict, or delete your personal data, and to object to certain processing. To exercise any of these rights, email privacy@guardrailhub.com — we respond within 30 days.",
      ],
    },
    {
      id: "international-transfers",
      heading: "International transfers",
      paragraphs: [
        "Where data moves across borders, we rely on the EU Standard Contractual Clauses and equivalent safeguards. Regional hosting options are on our roadmap and tracked publicly in the changelog.",
      ],
    },
    {
      id: "changes-and-contact",
      heading: "Changes and contact",
      paragraphs: [
        "We will notify account holders by email of material changes to this policy at least 14 days before they take effect. Questions? Contact our privacy team at privacy@guardrailhub.com, or write to Guardrail Hub, Inc., 2261 Market Street #4010, San Francisco, CA 94114, USA.",
      ],
    },
  ],
};
