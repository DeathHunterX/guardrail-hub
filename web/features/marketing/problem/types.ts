import type { LucideIcon } from "lucide-react";

export interface Pain {
  icon: LucideIcon;
  title: string;
  description: string;
  /** Which mini-illustration the card renders. */
  vignette: "sprawl" | "gluecode" | "findings" | "audit";
}
