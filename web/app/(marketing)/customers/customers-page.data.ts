/**
 * Copy for the dedicated /customers page — colocated data module per the
 * content convention. Testimonial quotes are shared with the landing
 * section via content/testimonials.ts; this file adds page-only framing.
 */

export const customersPageCopy = {
  eyebrow: "Customers",
  title: "Teams that ship faster because security keeps up",
  lede: "From six-person startups to platform teams with auditors on the calendar — here's what early adopters do with Guardrail Hub, in their own words.",
};

export const outcomeStats = [
  { value: "68%", label: "Less time-to-triage" },
  { value: "3×", label: "Fix throughput" },
  { value: "2 days", label: "Pentest prep (was 3 weeks)" },
  { value: "40", label: "Real issues from 1,800 alerts" },
];

export const customersCta = {
  title: "Become the next story",
  description:
    "Join the early-access program and see what your team's numbers look like — or talk it through with us on a demo first.",
  primary: { label: "Start Free", href: "/signup" },
  secondary: { label: "Book a demo", href: "/demo" },
};
