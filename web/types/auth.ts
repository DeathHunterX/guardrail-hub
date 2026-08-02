/** Cross-cutting auth/account types, consumed by services, hooks, and features. */

export type OAuthProvider = "google" | "microsoft" | "github" | "gitlab";

export type EnterpriseProtocol = "oidc" | "saml";

export interface EnterpriseIdentity {
  /** Display name of the identity provider, e.g. "Okta". */
  provider: string;
  protocol: EnterpriseProtocol;
  /** Verified domain the identity is scoped to, e.g. "acme.com". */
  domain: string;
}

export interface AuthUser {
  id: string;
  fullName: string;
  email: string;
  avatarUrl: string | null;
  /** IANA timezone identifier, e.g. "Europe/Berlin". */
  timezone: string;
  /** BCP 47 language tag, e.g. "en". */
  language: string;
  enterprise: EnterpriseIdentity | null;
}

export interface AuthSession {
  user: AuthUser;
  /** ISO timestamp of session creation. */
  createdAt: string;
  rememberMe: boolean;
}

export interface ConnectedAccount {
  provider: OAuthProvider;
  email: string;
  /** ISO timestamp; null when the provider was never linked. */
  connectedAt: string | null;
}

export interface ActiveSession {
  id: string;
  device: string;
  browser: string;
  location: string;
  /** ISO timestamp of last activity. */
  lastActiveAt: string;
  current: boolean;
}
