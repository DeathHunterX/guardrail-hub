import type { LucideIcon } from "lucide-react";

export interface Feature {
  icon: LucideIcon;
  title: string;
  description: string;
  size: "hero" | "wide" | "tall" | "standard";
  visual:
    | "chat"
    | "commits"
    | "dedupe"
    | "checklist"
    | "diff"
    | "pipeline"
    | "report"
    | "team"
    | "secrets"
    | "audit";
}
