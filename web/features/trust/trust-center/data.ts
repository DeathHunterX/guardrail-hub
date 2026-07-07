import {
  FileSearch,
  Fingerprint,
  KeyRound,
  Lock,
  ServerCog,
  ShieldCheck,
} from "lucide-react";

import type { Certification, Practice, Subprocessor } from "./types";

/** Copy for the Trust Center page — colocated data module per the content convention. */

export const trustCopy = {
  eyebrow: "Trust Center",
  title: "Security you can verify, not just read about",
  lede: "Certifications, security practices, and the subprocessor list — everything a security review needs, in one place. Reports and questionnaires available on request.",
  contactEmail: "trust@guardrailhub.com",
};

export const certifications: Certification[] = [
  {
    name: "SOC 2 Type II",
    status: "Report available under NDA",
    description:
      "Independent audit of our security, availability, and confidentiality controls over time. Request the latest report from the trust team.",
  },
  {
    name: "ISO 27001",
    status: "Certified",
    description:
      "Certified information security management system covering the platform, corporate systems, and the people who operate them.",
  },
  {
    name: "GDPR",
    status: "DPA + SCCs available",
    description:
      "EU data protection compliance with Standard Contractual Clauses for international transfers. Execute our DPA in one email.",
  },
];

export const practices: Practice[] = [
  {
    icon: Lock,
    title: "Encryption everywhere",
    description:
      "TLS 1.2+ for every connection, AES-256 at rest, and customer-scoped encryption keys for scan artifacts.",
  },
  {
    icon: KeyRound,
    title: "Access control",
    description:
      "SSO/SAML and SCIM provisioning, role-based access with least-privilege defaults, and hardware-key MFA for all staff.",
  },
  {
    icon: FileSearch,
    title: "Audit logging",
    description:
      "Every scan, configuration change, and data access is logged immutably and exportable to your SIEM.",
  },
  {
    icon: ServerCog,
    title: "Infrastructure isolation",
    description:
      "Logical tenant isolation for scan data, hardened build pipeline with signed artifacts, and infrastructure as code under review.",
  },
  {
    icon: ShieldCheck,
    title: "We scan ourselves",
    description:
      "Guardrail Hub runs continuously against our own services — the same scans, agents, and evidence trail we sell.",
  },
  {
    icon: Fingerprint,
    title: "Independent testing",
    description:
      "Annual third-party penetration tests plus a public responsible disclosure program with a 24-hour acknowledgement SLA.",
  },
];

export const subprocessors: Subprocessor[] = [
  { name: "Amazon Web Services", purpose: "Cloud infrastructure & storage", location: "United States / EU" },
  { name: "Vercel", purpose: "Website hosting & edge network", location: "United States" },
  { name: "Stripe", purpose: "Payment processing", location: "United States" },
  { name: "Postmark", purpose: "Transactional email", location: "United States" },
  { name: "Plausible Analytics", purpose: "Privacy-first web analytics", location: "European Union" },
];

export const trustLinks = [
  { label: "Privacy Policy", href: "/privacy" },
  { label: "Terms of Service", href: "/terms" },
  { label: "Data Processing Addendum", href: "/dpa" },
  { label: "Responsible Disclosure", href: "/security" },
];
