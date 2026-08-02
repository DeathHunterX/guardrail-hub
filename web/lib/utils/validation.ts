/** Form validation helpers shared by the auth and settings features. */

/** Pragmatic email shape check — the backend owns true validation. */
export function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value.trim());
}

export interface PasswordRequirement {
  id: string;
  label: string;
  test: (value: string) => boolean;
}

/** Displayed as a live checklist next to password fields. */
export const passwordRequirements: readonly PasswordRequirement[] = [
  {
    id: "length",
    label: "At least 8 characters",
    test: (value) => value.length >= 8,
  },
  {
    id: "uppercase",
    label: "One uppercase letter",
    test: (value) => /[A-Z]/.test(value),
  },
  {
    id: "lowercase",
    label: "One lowercase letter",
    test: (value) => /[a-z]/.test(value),
  },
  { id: "number", label: "One number", test: (value) => /\d/.test(value) },
  {
    id: "symbol",
    label: "One symbol",
    test: (value) => /[^A-Za-z0-9]/.test(value),
  },
];

export interface PasswordStrength {
  /** 0 (empty) to 4 (strong). */
  score: 0 | 1 | 2 | 3 | 4;
  label: "Empty" | "Weak" | "Fair" | "Good" | "Strong";
}

/** Requirement coverage mapped onto a 4-step meter. */
export function getPasswordStrength(value: string): PasswordStrength {
  if (!value) return { score: 0, label: "Empty" };
  const met = passwordRequirements.filter((rule) => rule.test(value)).length;
  if (met <= 2) return { score: 1, label: "Weak" };
  if (met === 3) return { score: 2, label: "Fair" };
  if (met === 4) return { score: 3, label: "Good" };
  return { score: 4, label: "Strong" };
}

export function isPasswordValid(value: string): boolean {
  return passwordRequirements.every((rule) => rule.test(value));
}
