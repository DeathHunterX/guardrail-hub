import { apiConfig } from "@/config/api";
import type { ServiceResult } from "@/types/api";
import type { AppPreferences, NotificationPreferences } from "@/types/settings";

/**
 * Settings service — application preferences and notification preferences.
 * Contract-first like the other services: bodies are MOCK TRANSPORTS to be
 * replaced with fetch calls to `apiConfig.endpoints.settings.*`.
 */

const MOCK_LATENCY_MS = 600;

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const defaultAppPreferences: AppPreferences = {
  defaultLandingPage: "/dashboard",
  density: "comfortable",
  showWelcomePanel: true,
};

export const defaultNotificationPreferences: NotificationPreferences = {
  email: {
    securityAlerts: true,
    operationDigest: true,
    weeklyReport: true,
    productUpdates: false,
  },
  inApp: {
    operationCompleted: true,
    findingAssigned: true,
    workerOffline: true,
  },
};

export async function getAppPreferences(): Promise<
  ServiceResult<AppPreferences>
> {
  // Backend integration: GET apiConfig.endpoints.settings.preferences
  void apiConfig;
  await delay(MOCK_LATENCY_MS);
  return { ok: true, data: defaultAppPreferences };
}

export async function updateAppPreferences(
  preferences: AppPreferences,
): Promise<ServiceResult<AppPreferences>> {
  // Backend integration: PUT apiConfig.endpoints.settings.preferences
  await delay(MOCK_LATENCY_MS);
  return { ok: true, data: preferences };
}

export async function getNotificationPreferences(): Promise<
  ServiceResult<NotificationPreferences>
> {
  // Backend integration: GET apiConfig.endpoints.settings.notifications
  await delay(MOCK_LATENCY_MS);
  return { ok: true, data: defaultNotificationPreferences };
}

export async function updateNotificationPreferences(
  preferences: NotificationPreferences,
): Promise<ServiceResult<NotificationPreferences>> {
  // Backend integration: PUT apiConfig.endpoints.settings.notifications
  await delay(MOCK_LATENCY_MS);
  return { ok: true, data: preferences };
}
