/**
 * Shared service-layer result contract. Services never throw across the UI
 * boundary — every call resolves to a discriminated union the caller can
 * exhaustively branch on (loading/error/success states in forms and pages).
 */
export interface ServiceError {
  /** Stable machine code the UI maps to copy — never shown raw. */
  code:
    | "invalid-credentials"
    | "invalid-otp"
    | "expired-otp"
    | "email-taken"
    | "network"
    | "server"
    | "unknown";
  /** Human-readable fallback message, safe to display. */
  message: string;
}

export type ServiceResult<T> =
  { ok: true; data: T } | { ok: false; error: ServiceError };

export const serviceError = (
  code: ServiceError["code"],
  message: string,
): { ok: false; error: ServiceError } => ({
  ok: false,
  error: { code, message },
});
