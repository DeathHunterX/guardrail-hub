import type { LucideIcon } from "lucide-react";

export interface WorkflowNode {
  id: string;
  icon: LucideIcon;
  label: string;
  role: string;
  stage: "ask" | "orchestrate" | "scan" | "validate" | "report" | "fix";
}

export interface WorkflowOutput {
  id: string;
  icon: LucideIcon;
  label: string;
  role: string;
}
