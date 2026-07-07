import type { LucideIcon } from "lucide-react";

export interface NavLink {
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

export interface NavMegaItem extends NavLink {
  description: string;
  icon: LucideIcon;
}

export interface NavGroup {
  label: string;
  items: NavMegaItem[];
}

export interface Navigation {
  groups: NavGroup[];
  links: NavLink[];
}

export interface Announcement {
  /** Bump the id to re-show the bar to users who dismissed a previous one. */
  id: string;
  message: string;
  shortMessage: string;
  linkLabel: string;
  href: string;
}
