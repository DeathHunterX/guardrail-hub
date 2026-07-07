/** Global site configuration — URLs, external links, and metadata defaults. */
export const siteConfig = {
  name: "Guardrail Hub",
  description:
    "AI-powered security validation. Guardrail Hub orchestrates scanners, frameworks, and compliance checks through a single AI agent — from first scan to signed report.",
  url: "https://guardrailhub.com",
  app: {
    signUp: "/signup",
    signIn: "/signin",
    bookDemo: "/demo",
  },
} as const;

export type SiteConfig = typeof siteConfig;
