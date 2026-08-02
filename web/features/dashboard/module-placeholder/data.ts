import {
  Blocks,
  FileText,
  FolderGit2,
  Gauge,
  LifeBuoy,
  Package,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

/** Copy for app modules whose backend hasn't shipped yet. */

export type PlaceholderModuleId =
  | "projects"
  | "operations"
  | "security"
  | "performance"
  | "reports"
  | "artifacts"
  | "integrations"
  | "help";

export interface PlaceholderModule {
  title: string;
  description: string;
  icon: LucideIcon;
}

export const placeholderModules: Record<
  PlaceholderModuleId,
  PlaceholderModule
> = {
  projects: {
    title: "Projects",
    description:
      "Organize scan targets, environments, and ownership per project. This module ships with the projects API.",
    icon: FolderGit2,
  },
  operations: {
    title: "Operations",
    description:
      "Launch, monitor, and replay security scans and test runs. This module ships with the operations API.",
    icon: Workflow,
  },
  security: {
    title: "Security",
    description:
      "Triage findings, track remediation, and review scanner coverage. This module ships with the findings API.",
    icon: ShieldCheck,
  },
  performance: {
    title: "Performance",
    description:
      "Design load tests and compare latency baselines across releases. This module ships with the JMeter engine API.",
    icon: Gauge,
  },
  reports: {
    title: "Reports",
    description:
      "Generate and share security, performance, and compliance reports. This module ships with the reporting API.",
    icon: FileText,
  },
  artifacts: {
    title: "Artifacts",
    description:
      "Browse raw scan output, HAR files, and evidence bundles. This module ships with the artifacts store.",
    icon: Package,
  },
  integrations: {
    title: "Integrations",
    description:
      "Connect CI/CD, Slack, and issue trackers to your workflows. This module ships with the integrations API.",
    icon: Blocks,
  },
  help: {
    title: "Help",
    description:
      "Searchable product docs and guided onboarding are on the way. Meanwhile, the public documentation covers the platform.",
    icon: LifeBuoy,
  },
};
