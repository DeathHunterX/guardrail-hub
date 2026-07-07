import type { LucideIcon } from "lucide-react";

export interface Certification {
  name: string;
  status: string;
  description: string;
}

export interface Practice {
  icon: LucideIcon;
  title: string;
  description: string;
}

export interface Subprocessor {
  name: string;
  purpose: string;
  location: string;
}
