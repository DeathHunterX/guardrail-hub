import type { AppPreferences } from "@/types/settings";

/** General settings option lists. */

export const landingPageOptions: {
  value: AppPreferences["defaultLandingPage"];
  label: string;
}[] = [
  { value: "/dashboard", label: "Dashboard" },
  { value: "/projects", label: "Projects" },
  { value: "/operations", label: "Operations" },
  { value: "/reports", label: "Reports" },
];

/** Future-ready placeholders — rendered disabled until each area ships. */
export const upcomingSettings = [
  {
    title: "API access",
    description: "Personal access tokens and workspace API keys.",
  },
  {
    title: "Data export",
    description: "Scheduled exports of findings and reports.",
  },
  {
    title: "Audit log",
    description: "Workspace-wide activity trail for admins.",
  },
] as const;
