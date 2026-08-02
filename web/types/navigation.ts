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

/** Sidebar / settings-nav entry inside the authenticated app shell. */
export interface AppNavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /**
   * Set while the module's backend does not exist yet — the route renders a
   * consistent "coming soon" state instead of a dead link.
   */
  planned?: boolean;
}

export interface AppNavSection {
  /** Optional group heading; omitted for the primary section. */
  label?: string;
  items: AppNavItem[];
}

/** Settings navigation reuses the shape without icons on sub-items. */
export interface SettingsNavGroup {
  label: string;
  items: { label: string; href: string; icon: LucideIcon }[];
}

export interface Announcement {
  /** Bump the id to re-show the bar to users who dismissed a previous one. */
  id: string;
  message: string;
  shortMessage: string;
  linkLabel: string;
  href: string;
}
