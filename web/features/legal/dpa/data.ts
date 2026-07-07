import type { LegalDoc } from "@/components/common/legal-article";

/**
 * Data Processing Addendum copy — colocated data module per the content
 * convention. NOTE: placeholder legal text for the pre-launch marketing
 * site; must be reviewed by counsel before general availability.
 */
export const dpaDoc: LegalDoc = {
  eyebrow: "Legal",
  title: "Data Processing Addendum",
  lede: "The processor terms that apply when Guardrail Hub processes personal data contained in Customer Content on your organization's behalf.",
  updated: "June 15, 2026",
  sections: [
    {
      id: "roles",
      heading: "Roles and scope",
      paragraphs: [
        "This Addendum forms part of the agreement between the customer (\"Controller\") and Guardrail Hub, Inc. (\"Processor\") and applies whenever personal data is contained in Customer Content processed by the Service — for example, personal data appearing in scanned repositories, target applications, or scan output.",
        "For account and billing data, Guardrail Hub acts as an independent controller as described in the Privacy Policy.",
      ],
    },
    {
      id: "processing-details",
      heading: "Details of processing",
      paragraphs: [
        "Subject matter: security scanning and validation of customer-designated targets. Duration: the term of the agreement plus the deletion window below. Nature and purpose: executing scans, generating findings and reports, and rendering dashboards. Data subjects and categories: determined by the Controller's content — typically end users or employees whose data appears in scanned systems.",
      ],
    },
    {
      id: "instructions",
      heading: "Processing on instructions",
      paragraphs: [
        "We process personal data only on the Controller's documented instructions — including scan configuration and retention settings — unless required otherwise by law, in which case we notify the Controller unless legally prohibited from doing so.",
      ],
    },
    {
      id: "confidentiality-security",
      heading: "Confidentiality and security",
      paragraphs: [
        "Personnel with access to Customer Content are bound by confidentiality obligations. We implement technical and organizational measures appropriate to the risk, including:",
      ],
      items: [
        "Encryption in transit (TLS 1.2+) and at rest (AES-256).",
        "Role-based access control with least-privilege defaults and audit logging.",
        "Logical tenant isolation for scan data and reports.",
        "Vulnerability management driven by our own platform, plus independent penetration testing.",
        "Documented incident response with Controller notification without undue delay, and no later than 72 hours after confirming a personal data breach.",
      ],
    },
    {
      id: "subprocessors",
      heading: "Subprocessors",
      paragraphs: [
        "The Controller authorizes the subprocessors listed in our Trust Center. We provide at least 30 days' notice before adding or replacing a subprocessor, during which the Controller may object on reasonable data-protection grounds. Subprocessors are bound by terms no less protective than this Addendum.",
      ],
    },
    {
      id: "data-subject-requests",
      heading: "Assistance and data subject requests",
      paragraphs: [
        "Taking into account the nature of processing, we assist the Controller with data subject requests, security of processing, breach notification, and data protection impact assessments. Requests received directly from data subjects are forwarded to the Controller without responding on the merits.",
      ],
    },
    {
      id: "transfers",
      heading: "International transfers",
      paragraphs: [
        "Transfers of personal data outside the EEA, UK, or Switzerland rely on the EU Standard Contractual Clauses (Module 2), which are incorporated into this Addendum by reference, together with the UK Addendum where applicable.",
      ],
    },
    {
      id: "deletion-audit",
      heading: "Deletion, return, and audits",
      paragraphs: [
        "Upon termination, we delete or return Customer Content at the Controller's choice within 30 days, excluding backups which age out within 35 days. We make available information reasonably necessary to demonstrate compliance, including audit summaries and certifications published in the Trust Center, and permit audits where required by law.",
        "To execute this Addendum or request a countersigned copy, contact legal@guardrailhub.com.",
      ],
    },
  ],
};
