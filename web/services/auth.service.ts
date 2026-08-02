import { apiConfig } from "@/config/api";
import { serviceError, type ServiceResult } from "@/types/api";
import type {
  AuthSession,
  AuthUser,
  EnterpriseProtocol,
  OAuthProvider,
} from "@/types/auth";

/**
 * Authentication service. The public functions are the stable contract the
 * auth features consume; every body below is a MOCK TRANSPORT to be replaced
 * with `fetch(apiConfig.baseUrl + apiConfig.endpoints.auth.*)` when the
 * backend ships. UI code must never need to change for that swap.
 *
 * Mock behavior (for exercising every UI state without a backend):
 * - password "wrong-password"  -> invalid-credentials
 * - password "network-error"   -> network failure
 * - password "server-error"    -> server failure
 * - email "taken@example.com"  -> email-taken on sign-up
 * - OTP "000000"               -> invalid-otp; OTP "999999" -> expired-otp
 * - anything else succeeds; any 6-digit OTP other than the above verifies
 */

const MOCK_LATENCY_MS = 900;

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function mockUser(email: string, fullName?: string): AuthUser {
  const namePart = email.split("@")[0] ?? "user";
  return {
    id: "usr_demo_001",
    fullName:
      fullName ??
      namePart
        .split(/[._-]/)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" "),
    email,
    avatarUrl: null,
    timezone: "UTC",
    language: "en",
    enterprise: null,
  };
}

function mockSession(user: AuthUser, rememberMe: boolean): AuthSession {
  return { user, createdAt: new Date().toISOString(), rememberMe };
}

export interface SignInInput {
  email: string;
  password: string;
  rememberMe: boolean;
}

export async function signIn(
  input: SignInInput,
): Promise<ServiceResult<AuthSession>> {
  // Backend integration: POST apiConfig.endpoints.auth.signIn
  void apiConfig;
  await delay(MOCK_LATENCY_MS);
  switch (input.password) {
    case "wrong-password":
      return serviceError(
        "invalid-credentials",
        "Incorrect email or password. Check your credentials and try again.",
      );
    case "network-error":
      return serviceError(
        "network",
        "We couldn't reach the server. Check your connection and try again.",
      );
    case "server-error":
      return serviceError(
        "server",
        "Something went wrong on our side. Please try again in a moment.",
      );
    default:
      return {
        ok: true,
        data: mockSession(mockUser(input.email), input.rememberMe),
      };
  }
}

export interface SignUpInput {
  fullName: string;
  email: string;
  password: string;
}

export async function signUp(
  input: SignUpInput,
): Promise<ServiceResult<AuthSession>> {
  // Backend integration: POST apiConfig.endpoints.auth.signUp
  await delay(MOCK_LATENCY_MS);
  if (input.email.toLowerCase() === "taken@example.com") {
    return serviceError(
      "email-taken",
      "An account with this email already exists. Try signing in instead.",
    );
  }
  return {
    ok: true,
    data: mockSession(mockUser(input.email, input.fullName), true),
  };
}

export async function signInWithOAuth(
  provider: OAuthProvider,
): Promise<ServiceResult<AuthSession>> {
  // Backend integration: redirect to apiConfig.endpoints.auth.oauth with the
  // provider id — the real flow is a full-page OAuth2 redirect, not fetch.
  await delay(MOCK_LATENCY_MS);
  const emails: Record<OAuthProvider, string> = {
    google: "demo@gmail.com",
    microsoft: "demo@outlook.com",
    github: "demo@github.com",
    gitlab: "demo@gitlab.com",
  };
  return { ok: true, data: mockSession(mockUser(emails[provider]), true) };
}

export interface EnterpriseSignInInput {
  email: string;
  protocol: EnterpriseProtocol;
}

export async function signInWithEnterprise(
  input: EnterpriseSignInInput,
): Promise<ServiceResult<AuthSession>> {
  // Backend integration: POST apiConfig.endpoints.auth.enterprise, then a
  // full-page redirect to the tenant IdP.
  await delay(MOCK_LATENCY_MS);
  const user = mockUser(input.email);
  const domain = input.email.split("@")[1] ?? "example.com";
  return {
    ok: true,
    data: mockSession(
      {
        ...user,
        enterprise: {
          provider: input.protocol === "saml" ? "Okta" : "Entra ID",
          protocol: input.protocol,
          domain,
        },
      },
      true,
    ),
  };
}

export async function requestPasswordReset(
  email: string,
): Promise<ServiceResult<{ resendAfterSeconds: number }>> {
  // Backend integration: POST apiConfig.endpoints.auth.forgotPassword
  await delay(MOCK_LATENCY_MS);
  if (email.toLowerCase() === "network@example.com") {
    return serviceError(
      "network",
      "We couldn't reach the server. Check your connection and try again.",
    );
  }
  return { ok: true, data: { resendAfterSeconds: 30 } };
}

export async function verifyOtp(
  email: string,
  code: string,
): Promise<ServiceResult<{ resetToken: string }>> {
  // Backend integration: POST apiConfig.endpoints.auth.verifyOtp
  await delay(MOCK_LATENCY_MS);
  if (code === "000000") {
    return serviceError(
      "invalid-otp",
      "That code is not valid. Check the code and try again.",
    );
  }
  if (code === "999999") {
    return serviceError(
      "expired-otp",
      "That code has expired. Request a new one below.",
    );
  }
  return { ok: true, data: { resetToken: `reset_${email}_${Date.now()}` } };
}

export async function resetPassword(input: {
  resetToken: string;
  password: string;
}): Promise<ServiceResult<null>> {
  // Backend integration: POST apiConfig.endpoints.auth.resetPassword
  await delay(MOCK_LATENCY_MS);
  void input;
  return { ok: true, data: null };
}

export async function signOut(): Promise<ServiceResult<null>> {
  // Backend integration: POST apiConfig.endpoints.auth.signOut
  await delay(200);
  return { ok: true, data: null };
}
