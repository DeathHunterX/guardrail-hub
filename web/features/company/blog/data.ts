import type { BlogPost } from "./types";

/** Copy for the Blog page — colocated data module per the content convention. */

export const blogCopy = {
  eyebrow: "Blog",
  title: "Notes from the guardrail",
  lede: "Engineering deep-dives, security research, and progress reports from the team building Guardrail Hub. First posts publish alongside our public launch.",
};

/**
 * Upcoming posts — the product is pre-launch, so these render as a preview
 * of the editorial calendar rather than linked articles.
 */
export const posts: BlogPost[] = [
  {
    title: "Teaching an AI agent to drive OWASP ZAP",
    excerpt:
      "How we wrapped ZAP in an MCP server so a language model can plan, run, and interpret baseline scans — and where tool-calling breaks down when a scan takes twenty minutes.",
    date: "Coming at launch",
    readingTime: "12 min read",
    tag: "Engineering",
    author: { name: "Minh Tran", role: "Founding Engineer" },
    featured: true,
  },
  {
    title: "Why every scanner speaks a different language",
    excerpt:
      "SARIF, JSON, XML, plain text: a tour of security tool output formats and the normalization layer we built to make findings comparable.",
    date: "Coming at launch",
    readingTime: "8 min read",
    tag: "Engineering",
    author: { name: "Sofia Alvarez", role: "Platform Engineer" },
  },
  {
    title: "Compliance evidence that writes itself",
    excerpt:
      "Mapping scan results to SOC 2 and ISO 27001 controls automatically — what works, what needs a human, and why we refuse to fabricate a passing status.",
    date: "Coming at launch",
    readingTime: "10 min read",
    tag: "Product",
    author: { name: "Priya Nair", role: "Product" },
  },
  {
    title: "The pre-launch security checklist we actually use",
    excerpt:
      "A practical, opinionated checklist for teams shipping their first production release — the same one we run against Guardrail Hub itself.",
    date: "Coming at launch",
    readingTime: "6 min read",
    tag: "Security",
    author: { name: "Daniel Okafor", role: "Security Engineer" },
  },
  {
    title: "Building in the open: our first three releases",
    excerpt:
      "A look back at v0.1.0 through v0.3.0 — what shipped, what slipped, and how a public changelog keeps an early-stage product honest.",
    date: "Coming at launch",
    readingTime: "7 min read",
    tag: "Company",
    author: { name: "Minh Tran", role: "Founding Engineer" },
  },
  {
    title: "MCP in production: lessons from our server",
    excerpt:
      "Patterns and anti-patterns from running a Model Context Protocol server that exposes real security tooling to AI agents.",
    date: "Coming at launch",
    readingTime: "9 min read",
    tag: "Engineering",
    author: { name: "Sofia Alvarez", role: "Platform Engineer" },
  },
];

export const blogCta = {
  title: "Be first to read",
  description:
    "Follow development on GitHub or join the Discord — we announce every post and release in both places.",
};
