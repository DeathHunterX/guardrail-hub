/**
 * Backend API configuration. The base URL comes from the environment so no
 * service ever hardcodes a host; endpoint paths live here so services and
 * tests share a single source of truth (frontend-config-content R5).
 *
 * The backend does not exist yet — services currently return mock data and
 * only reference these paths, so integration later is a transport swap.
 */
export const apiConfig = {
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1",
  endpoints: {
    auth: {
      signIn: "/auth/sign-in",
      signUp: "/auth/sign-up",
      signOut: "/auth/sign-out",
      /** `:provider` is replaced with an OAuthProvider id. */
      oauth: "/auth/oauth/:provider",
      /** Generic enterprise IdP entry — OIDC and SAML negotiate server-side. */
      enterprise: "/auth/enterprise",
      forgotPassword: "/auth/forgot-password",
      verifyOtp: "/auth/verify-otp",
      resetPassword: "/auth/reset-password",
    },
    account: {
      profile: "/account/profile",
      password: "/account/password",
      sessions: "/account/sessions",
      connectedAccounts: "/account/connected-accounts",
    },
    settings: {
      preferences: "/settings/preferences",
      notifications: "/settings/notifications",
    },
  },
} as const;

export type ApiConfig = typeof apiConfig;
