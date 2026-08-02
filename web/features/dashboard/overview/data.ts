import {
  Activity,
  FileText,
  FolderGit2,
  Gauge,
  ListTodo,
  Play,
  ServerCog,
  ShieldAlert,
  TimerReset,
  UserPlus,
  Workflow,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { DashboardMetricId } from "@/types/dashboard";

/** Overview copy + presentation mappings (icons stay out of the service layer). */

export const overviewCopy = {
  welcome: {
    eyebrow: "Overview",
    /** `{name}` is replaced with the user's first name. */
    greeting: "Welcome back, {name}",
    lede: "Here's what's happening across your security and performance operations.",
  },
  quickActionsTitle: "Quick actions",
} as const;

export const metricIcons: Record<DashboardMetricId, LucideIcon> = {
  projects: FolderGit2,
  "running-operations": Workflow,
  "queued-operations": ListTodo,
  "successful-executions": Activity,
  "failed-executions": XCircle,
  "online-workers": ServerCog,
  "security-findings": ShieldAlert,
  "performance-tests": Gauge,
};

export interface QuickAction {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const quickActions: QuickAction[] = [
  { label: "Run security scan", href: "/operations", icon: Play },
  { label: "Start load test", href: "/performance", icon: TimerReset },
  { label: "Generate report", href: "/reports", icon: FileText },
  { label: "Invite teammate", href: "/settings/general", icon: UserPlus },
];
