/** Global site configuration — URLs, external links, and metadata defaults. */
export const siteConfig = {
  name: "Guardrail Hub",
  description:
    "AI-powered security validation. Guardrail Hub orchestrates scanners, frameworks, and compliance checks through a single AI agent — from first scan to signed report.",
  url: "https://guardrailhub.com",
  links: {
    github: "https://github.com/guardrail-hub/guardrail-hub",
    githubRepo: "guardrail-hub/guardrail-hub",
    docs: "https://docs.guardrailhub.com",
    x: "https://x.com/guardrailhub",
    linkedin: "https://www.linkedin.com/company/guardrailhub",
    discord: "https://discord.gg/guardrailhub",
    youtube: "https://www.youtube.com/@guardrailhub",
    status: "https://status.guardrailhub.com",
  },
  app: {
    signUp: "/signup",
    signIn: "/signin",
    bookDemo: "/demo",
  },
} as const;

export type SiteConfig = typeof siteConfig;
