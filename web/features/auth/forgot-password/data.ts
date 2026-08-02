/** Forgot-password flow copy, one block per step. */
export const forgotPasswordCopy = {
  email: {
    title: "Reset your password",
    description:
      "Enter the email for your account and we'll send a one-time code.",
    cta: "Send code",
  },
  otp: {
    title: "Check your email",
    descriptionPrefix: "We sent a 6-digit code to",
    cta: "Verify code",
    resend: "Resend code",
    resendCountdown: "Resend available in",
  },
  reset: {
    title: "Choose a new password",
    description: "Your new password must meet all of the requirements below.",
    cta: "Reset password",
  },
  success: {
    title: "Password reset",
    description:
      "Your password has been updated. Sign in with your new password to continue.",
    cta: "Return to sign in",
  },
  footer: {
    prompt: "Remembered it after all?",
    linkLabel: "Back to sign in",
  },
} as const;

/** The resend window (seconds) comes from the service response. */
export const OTP_LENGTH = 6;
