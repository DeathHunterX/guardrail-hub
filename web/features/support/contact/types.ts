import type { LucideIcon } from "lucide-react";

export interface ContactChannel {
  icon: LucideIcon;
  title: string;
  description: string;
  action: { label: string; href: string; external?: boolean };
}
