import { externalLinks } from "@/constants/external-links";

export interface FooterLink {
  label: string;
  href: string;
  external?: boolean;
  /**
   * Alternate destination when the visitor is on the landing page — used by
   * links whose primary href is a dedicated page but which should scroll to
   * the equivalent landing section when one is in view (e.g. Pricing).
   */
  landingHref?: string;
}

export interface FooterGroup {
  heading: string;
  links: FooterLink[];
}

export const footerGroups: FooterGroup[] = [
  {
    heading: "Product",
    links: [
      // "/#" anchors resolve from any route: they navigate home first when
      // needed, then scroll to the section.
      { label: "Features", href: "/#features" },
      { label: "AI Agents", href: "/#agent" },
      { label: "Dashboard", href: "/#showcase" },
      { label: "Integrations", href: "/#integrations" },
      // On the landing page Pricing scrolls to the section; everywhere else
      // it opens the dedicated /pricing page.
      { label: "Pricing", href: "/pricing", landingHref: "#pricing" },
      { label: "Changelog", href: "/changelog" },
    ],
  },
  {
    heading: "Developers",
    links: [
      { label: "Documentation", href: externalLinks.docs, external: true },
      { label: "API Reference", href: `${externalLinks.docs}/api`, external: true },
      { label: "CLI", href: `${externalLinks.docs}/cli`, external: true },
      { label: "GitHub", href: externalLinks.github, external: true },
      { label: "Community", href: externalLinks.discord, external: true },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Blog", href: "/blog" },
      { label: "Careers", href: "/careers" },
      // On the landing page Customers scrolls to the testimonials section;
      // everywhere else it opens the dedicated /customers page.
      { label: "Customers", href: "/customers", landingHref: "#testimonials" },
      { label: "Support", href: "/support" },
      { label: "Contact", href: "/contact" },
    ],
  },
  {
    heading: "Legal & Trust",
    links: [
      { label: "Privacy", href: "/privacy" },
      { label: "Terms", href: "/terms" },
      { label: "DPA", href: "/dpa" },
      { label: "Trust Center", href: "/trust" },
      { label: "Responsible Disclosure", href: "/security" },
    ],
  },
];

export const footerTagline =
  "AI-powered security validation for teams that ship.";
