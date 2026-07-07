import type { LucideIcon } from "lucide-react";

export interface Capability {
  icon: LucideIcon;
  lead: string;
  text: string;
}

export interface ScenarioBlock {
  type: "text" | "tools" | "table" | "badge";
  text?: string;
  tools?: string[];
  rows?: Array<{ label: string; value: string }>;
  badge?: { label: string; variant: "success" | "warning" | "destructive" };
}

export interface Scenario {
  id: string;
  chip: string;
  user: string;
  blocks: ScenarioBlock[];
}

export interface AgentStat {
  value: string;
  label: string;
}
