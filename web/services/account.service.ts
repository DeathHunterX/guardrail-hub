import { apiConfig } from "@/config/api";
import { serviceError, type ServiceResult } from "@/types/api";
import type {
  ActiveSession,
  AuthUser,
  ConnectedAccount,
  OAuthProvider,
} from "@/types/auth";

/**
 * Account service — profile, password, sessions, connected accounts.
 * Same contract-first shape as auth.service.ts: the exported functions are
 * stable; each body is a MOCK TRANSPORT to be replaced with fetch calls to
 * `apiConfig.endpoints.account.*` when the backend ships.
 */

const MOCK_LATENCY_MS = 700;

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export interface UpdateProfileInput {
  fullName: string;
  timezone: string;
  language: string;
}

export async function updateProfile(
  input: UpdateProfileInput,
): Promise<
  ServiceResult<Pick<AuthUser, "fullName" | "timezone" | "language">>
> {
  // Backend integration: PATCH apiConfig.endpoints.account.profile
  void apiConfig;
  await delay(MOCK_LATENCY_MS);
  return { ok: true, data: input };
}

export interface ChangePasswordInput {
  currentPassword: string;
  newPassword: string;
}

export async function changePassword(
  input: ChangePasswordInput,
): Promise<ServiceResult<null>> {
  // Backend integration: PUT apiConfig.endpoints.account.password
  await delay(MOCK_LATENCY_MS);
  if (input.currentPassword === "wrong-password") {
    return serviceError(
      "invalid-credentials",
      "Your current password is incorrect.",
    );
  }
  return { ok: true, data: null };
}

export async function getActiveSessions(): Promise<
  ServiceResult<ActiveSession[]>
> {
  // Backend integration: GET apiConfig.endpoints.account.sessions
  await delay(MOCK_LATENCY_MS);
  const now = Date.now();
  const hoursAgo = (h: number) => new Date(now - h * 3_600_000).toISOString();
  return {
    ok: true,
    data: [
      {
        id: "ses_001",
        device: "MacBook Pro",
        browser: "Chrome 138 · macOS",
        location: "Berlin, Germany",
        lastActiveAt: hoursAgo(0),
        current: true,
      },
      {
        id: "ses_002",
        device: "iPhone 16",
        browser: "Safari · iOS 19",
        location: "Berlin, Germany",
        lastActiveAt: hoursAgo(5),
        current: false,
      },
      {
        id: "ses_003",
        device: "Work desktop",
        browser: "Edge 138 · Windows 11",
        location: "Munich, Germany",
        lastActiveAt: hoursAgo(72),
        current: false,
      },
    ],
  };
}

export async function revokeSession(
  sessionId: string,
): Promise<ServiceResult<null>> {
  // Backend integration: DELETE apiConfig.endpoints.account.sessions/:id
  await delay(MOCK_LATENCY_MS);
  void sessionId;
  return { ok: true, data: null };
}

export async function getConnectedAccounts(): Promise<
  ServiceResult<ConnectedAccount[]>
> {
  // Backend integration: GET apiConfig.endpoints.account.connectedAccounts
  await delay(MOCK_LATENCY_MS);
  return {
    ok: true,
    data: [
      {
        provider: "google",
        email: "demo@gmail.com",
        connectedAt: "2026-05-14T09:30:00.000Z",
      },
      { provider: "microsoft", email: "", connectedAt: null },
      { provider: "github", email: "", connectedAt: null },
      { provider: "gitlab", email: "", connectedAt: null },
    ],
  };
}

export async function connectAccount(
  provider: OAuthProvider,
): Promise<ServiceResult<ConnectedAccount>> {
  // Backend integration: OAuth2 redirect via apiConfig.endpoints.auth.oauth
  await delay(MOCK_LATENCY_MS);
  return {
    ok: true,
    data: {
      provider,
      email: `demo@${provider === "google" ? "gmail" : provider}.com`,
      connectedAt: new Date().toISOString(),
    },
  };
}

export async function disconnectAccount(
  provider: OAuthProvider,
): Promise<ServiceResult<null>> {
  // Backend integration: DELETE apiConfig.endpoints.account.connectedAccounts/:provider
  await delay(MOCK_LATENCY_MS);
  void provider;
  return { ok: true, data: null };
}
