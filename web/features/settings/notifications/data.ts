import type {
  AppNotificationPreferences,
  EmailNotificationPreferences,
} from "@/types/settings";

/** Notification toggle definitions — labels for each preference key. */

export const emailPreferenceItems: {
  key: keyof EmailNotificationPreferences;
  label: string;
  description: string;
}[] = [
  {
    key: "securityAlerts",
    label: "Security alerts",
    description: "Critical and high findings the moment they're confirmed.",
  },
  {
    key: "operationDigest",
    label: "Operation digest",
    description: "Daily summary of completed scans and test runs.",
  },
  {
    key: "weeklyReport",
    label: "Weekly report",
    description: "Posture and performance trends, every Monday.",
  },
  {
    key: "productUpdates",
    label: "Product updates",
    description: "New features, integrations, and changelog highlights.",
  },
];

export const appPreferenceItems: {
  key: keyof AppNotificationPreferences;
  label: string;
  description: string;
}[] = [
  {
    key: "operationCompleted",
    label: "Operation completed",
    description: "When a scan or load test you started finishes.",
  },
  {
    key: "findingAssigned",
    label: "Finding assigned",
    description: "When a finding is assigned to you for remediation.",
  },
  {
    key: "workerOffline",
    label: "Worker offline",
    description: "When a worker drops out of the pool.",
  },
];
