import {
  Bug,
  CalendarClock,
  LifeBuoy,
  Mail,
  MessageCircle,
  Newspaper,
} from "lucide-react";

import { siteConfig } from "@/config/site";
import { externalLinks } from "@/constants/external-links";

import type { ContactChannel } from "./types";

/** Copy for the Contact page — colocated data module per the content convention. */

export const contactCopy = {
  eyebrow: "Contact",
  title: "Talk to a human",
  lede: "Sales questions, support, security reports, or just curious about the roadmap — pick the channel and we'll take it from there.",
};

export const channels: ContactChannel[] = [
  {
    icon: CalendarClock,
    title: "Sales & demos",
    description:
      "See the platform on your own codebase. 30 minutes, no slideware — a live scan and an honest look at what's ready today.",
    action: { label: "Book a demo", href: siteConfig.app.bookDemo },
  },
  {
    icon: LifeBuoy,
    title: "Support",
    description:
      "Something broken or confusing? Check the help center for common cases — early-access users get answers directly from the engineers who built the thing.",
    action: {
      label: "Visit the help center",
      href: "/support",
    },
  },
  {
    icon: Bug,
    title: "Security reports",
    description:
      "Found a vulnerability in Guardrail Hub itself? Please use our responsible disclosure process — we take these seriously and respond fast.",
    action: { label: "Responsible disclosure", href: "/security" },
  },
  {
    icon: MessageCircle,
    title: "Community",
    description:
      "The fastest way to reach the team and other early adopters. Release announcements, roadmap threads, and office hours.",
    action: {
      label: "Join the Discord",
      href: externalLinks.discord,
      external: true,
    },
  },
  {
    icon: Newspaper,
    title: "Press & partnerships",
    description:
      "Writing about AI-driven security, or want to integrate with the platform? We'd love to hear from you.",
    action: {
      label: "press@guardrailhub.com",
      href: "mailto:press@guardrailhub.com",
    },
  },
  {
    icon: Mail,
    title: "Everything else",
    description:
      "Not sure where it fits? Send it to the general inbox and we'll route it to the right person — usually within one business day.",
    action: {
      label: "hello@guardrailhub.com",
      href: "mailto:hello@guardrailhub.com",
    },
  },
];

export const responseNote =
  "We're a small team across several time zones. Expect a reply within one business day — security reports get acknowledged within 24 hours.";
