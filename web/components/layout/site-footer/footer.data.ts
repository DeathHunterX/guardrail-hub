import { siteConfig } from "@/config/site";

export interface FooterLink {
  label: string;
  href: string;
  external?: boolean;
}

export interface FooterGroup {
  heading: string;
  links: FooterLink[];
}

export const footerGroups: FooterGroup[] = [
  {
    heading: "Product",
    links: [
      { label: "Features", href: "#features" },
      { label: "AI Agents", href: "#agent" },
      { label: "Dashboard", href: "#showcase" },
      { label: "Integrations", href: "#integrations" },
      { label: "Pricing", href: "#pricing" },
      { label: "Changelog", href: `${siteConfig.links.github}/releases`, external: true },
    ],
  },
  {
    heading: "Developers",
    links: [
      { label: "Documentation", href: siteConfig.links.docs, external: true },
      { label: "API Reference", href: `${siteConfig.links.docs}/api`, external: true },
      { label: "CLI", href: `${siteConfig.links.docs}/cli`, external: true },
      { label: "GitHub", href: siteConfig.links.github, external: true },
      { label: "Community", href: siteConfig.links.discord, external: true },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Blog", href: "/blog" },
      { label: "Careers", href: "/careers" },
      { label: "Customers", href: "#testimonials" },
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
