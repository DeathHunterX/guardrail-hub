/** Cross-cutting settings types, consumed by the settings service and features. */

export interface AppPreferences {
  /** Route the user lands on after signing in. */
  defaultLandingPage: "/dashboard" | "/projects" | "/operations" | "/reports";
  /** Dashboard widget density. */
  density: "comfortable" | "compact";
  /** Show the welcome/getting-started panel on the dashboard. */
  showWelcomePanel: boolean;
}

export interface EmailNotificationPreferences {
  securityAlerts: boolean;
  operationDigest: boolean;
  weeklyReport: boolean;
  productUpdates: boolean;
}

export interface AppNotificationPreferences {
  operationCompleted: boolean;
  findingAssigned: boolean;
  workerOffline: boolean;
}

export interface NotificationPreferences {
  email: EmailNotificationPreferences;
  inApp: AppNotificationPreferences;
}
