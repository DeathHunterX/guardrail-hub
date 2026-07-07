/** Copy for the Responsible Disclosure page — colocated data module per the content convention. */

export const securityCopy = {
  eyebrow: "Responsible Disclosure",
  title: "Found a vulnerability? Tell us first.",
  lede: "We build a security product, so we hold ourselves to the standard we sell. If you've found a weakness in Guardrail Hub, we want to hear about it — safely, legally, and with our thanks.",
  reportEmail: "security@guardrailhub.com",
  pgpNote:
    "Encrypt sensitive reports with our PGP key, published at guardrailhub.com/.well-known/security.txt.",
};

export const responseTimeline = [
  { label: "Acknowledgement", value: "24 hours" },
  { label: "Triage & severity", value: "72 hours" },
  { label: "Status updates", value: "Every 7 days" },
  { label: "Fix target (critical)", value: "30 days" },
];

export const inScope = [
  "guardrailhub.com and all first-party subdomains (app, api, docs, status).",
  "The Guardrail Hub platform, APIs, and open-source MCP server.",
  "Official client libraries and CLI published under the guardrail-hub organization.",
];

export const outOfScope = [
  "Denial-of-service, volumetric, or resource-exhaustion testing.",
  "Social engineering, phishing, or physical attacks against staff or infrastructure.",
  "Third-party services we use (report to the vendor; we'll help coordinate).",
  "Automated scanner output without a demonstrated, reproducible impact.",
  "Clickjacking, missing security headers, or SPF/DMARC records without an exploit path.",
];

export const reportGuidelines = [
  "Describe the issue, the affected endpoint or component, and reproduction steps.",
  "Include the impact you believe is possible — we triage on demonstrated impact.",
  "Limit testing to accounts you own; never access, modify, or exfiltrate another user's data.",
  "Give us reasonable time to remediate before any public disclosure — we default to a 90-day coordinated window.",
];

export const safeHarbor = {
  heading: "Safe harbor",
  paragraphs: [
    "We will not pursue legal action against researchers who act in good faith: staying within scope, avoiding privacy violations and service disruption, and reporting promptly through this process. If a third party initiates action against you for research that complied with this policy, we will make it known that your activities were authorized.",
    "We currently thank researchers publicly (with permission) in our hall of fame and offer swag for valid reports. A paid bounty program is planned and will be announced in the changelog.",
  ],
};
