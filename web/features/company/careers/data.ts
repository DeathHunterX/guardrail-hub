import {
  Globe2,
  HeartPulse,
  Laptop,
  PiggyBank,
  Plane,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

/** Copy for the Careers page — colocated data module per the content convention. */

export const careersCopy = {
  eyebrow: "Careers",
  title: "Build the security platform you wish you had",
  lede: "We're a small, remote-first team shipping an AI-powered security product in the open. Early enough that your fingerprints will be on everything; funded enough to pay properly for it.",
  applyEmail: "careers@guardrailhub.com",
};

export interface Benefit {
  icon: LucideIcon;
  title: string;
  description: string;
}

export const benefits: Benefit[] = [
  {
    icon: Globe2,
    title: "Remote-first, always",
    description:
      "Work from anywhere between UTC-8 and UTC+10. We overlap four hours a day and write everything else down.",
  },
  {
    icon: PiggyBank,
    title: "Meaningful equity",
    description:
      "Early-stage ownership with founder-friendly terms extended to every hire — 10-year exercise windows included.",
  },
  {
    icon: Laptop,
    title: "Gear and workspace budget",
    description:
      "A new laptop on day one plus an annual budget for your home office or a co-working space near you.",
  },
  {
    icon: HeartPulse,
    title: "Health cover, wherever you are",
    description:
      "Private health insurance or a local-equivalent stipend, matched to your country of residence.",
  },
  {
    icon: Plane,
    title: "Two offsites a year",
    description:
      "The whole team, one place, twice a year — half roadmap, half getting to know the humans behind the avatars.",
  },
  {
    icon: Sparkles,
    title: "Ship in the open",
    description:
      "Your work lands in a public changelog and an open-source MCP server. Portfolio-building is a side effect of the job.",
  },
];

export interface OpenRole {
  title: string;
  team: "Engineering" | "Design" | "Go-to-market";
  location: string;
  type: string;
  summary: string;
}

export const roles: OpenRole[] = [
  {
    title: "Senior Backend Engineer (Python)",
    team: "Engineering",
    location: "Remote",
    type: "Full-time",
    summary:
      "Own the FastAPI MCP server that orchestrates our scanners — from tool contracts to scan lifecycle, reporting, and the data layer beneath it.",
  },
  {
    title: "Senior Frontend Engineer (React / Next.js)",
    team: "Engineering",
    location: "Remote",
    type: "Full-time",
    summary:
      "Take the product from marketing site to dashboard: findings views, scan timelines, and the compliance matrix — fast, accessible, and beautiful.",
  },
  {
    title: "Security Engineer (Offensive)",
    team: "Engineering",
    location: "Remote",
    type: "Full-time",
    summary:
      "Teach the agent what a real attacker does. Design scan strategies, validate findings, and keep our own attack surface honest.",
  },
  {
    title: "Founding Product Designer",
    team: "Design",
    location: "Remote",
    type: "Full-time",
    summary:
      "Define how a security product feels when it's built for developers first — from design system to the dashboard's information architecture.",
  },
  {
    title: "Developer Advocate",
    team: "Go-to-market",
    location: "Remote",
    type: "Full-time",
    summary:
      "Write the deep-dives, run the community, and feed what developers actually struggle with back into the roadmap.",
  },
];

export const hiringProcess = [
  "Intro call (30 min) — mutual fit, your questions first.",
  "Technical deep-dive (60–90 min) — a conversation about real work, not whiteboard puzzles.",
  "Paid work sample — a scoped, compensated task done on your schedule.",
  "Team fit + offer — meet the people you'd work with, then a decision within 48 hours.",
];
