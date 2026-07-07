/**
 * Testimonial data — shared marketing copy (architecture §12). Lives in
 * content/ because two surfaces render it: the landing testimonials section
 * and the dedicated /customers page.
 */

import type { Testimonial } from "@/types/marketing";

export const testimonialsCopy = {
  eyebrow: "Loved by teams who ship",
  title: "Don't take our word for it.",
} as const;

export const featured: Testimonial = {
  quote:
    "We replaced four security consoles and a quarterly pentest scramble with one agent. Our board report went from a two-week fire drill to a button.",
  name: "Elena Vasquez",
  role: "CTO",
  company: "Nortcloud",
  metric: "Pentest prep: 3 weeks → 2 days",
};

export const testimonials: Testimonial[] = [
  {
    quote: "I type 'check the release branch' in Slack and get a ranked findings list before code review ends.",
    name: "Daniel Okafor",
    role: "Senior Developer",
    company: "Kitewire",
    metric: "↓ 68% time-to-triage",
  },
  {
    quote: "The dedup alone paid for it. 1,800 raw alerts became 40 real issues with owners and SLAs.",
    name: "Mira Chen",
    role: "DevSecOps Engineer",
    company: "Signalbay",
  },
  {
    quote: "Our QA suite now includes security scenarios we describe in plain English. No YAML.",
    name: "Tomás Ribeiro",
    role: "QA Lead",
    company: "Parcelio",
    metric: "0 config files",
  },
  {
    quote: "SOC 2 evidence collection used to be my Q3. Now it's a Tuesday afternoon.",
    name: "Sarah Lindqvist",
    role: "Security Engineer",
    company: "Lumenard",
  },
  {
    quote: "We're a six-person startup with enterprise-grade security posture. That sentence didn't parse before Guardrail.",
    name: "Ade Bakare",
    role: "Founder",
    company: "Hexlane",
  },
  {
    quote: "The agent explains findings so well our juniors stopped pinging me for every CVE.",
    name: "Katya Novak",
    role: "Staff Engineer",
    company: "Drayven",
    metric: "↑ 3× fix throughput",
  },
];
