"use client";

import { AlertCircle, CheckCircle2, Loader2, MailCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AuthCard } from "@/components/common/auth-card";
import { OtpInput } from "@/components/common/otp-input";
import { PasswordInput } from "@/components/common/password-input";
import { PasswordStrength } from "@/components/common/password-strength";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { siteConfig } from "@/config/site";
import { useCountdown } from "@/hooks/use-countdown";
import { isPasswordValid, isValidEmail } from "@/lib/utils";
import {
  requestPasswordReset,
  resetPassword,
  verifyOtp,
} from "@/services/auth.service";
import type { ServiceError } from "@/types/api";

import { OTP_LENGTH, forgotPasswordCopy as copy } from "./data";

type Step = "email" | "otp" | "reset" | "success";

export function ForgotPassword() {
  const router = useRouter();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [formError, setFormError] = useState<ServiceError | null>(null);
  const [pending, setPending] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);

  const { remaining, restart } = useCountdown(0);

  useEffect(() => {
    if (formError) errorRef.current?.focus();
  }, [formError]);

  const clearErrors = () => {
    setFormError(null);
    setFieldError(null);
    setConfirmError(null);
  };

  /* Step 1 — request the code. */
  const handleSendCode = async (event: React.FormEvent) => {
    event.preventDefault();
    clearErrors();
    if (!isValidEmail(email)) {
      setFieldError("Enter a valid email address.");
      return;
    }
    setPending(true);
    const result = await requestPasswordReset(email);
    setPending(false);
    if (result.ok) {
      restart(result.data.resendAfterSeconds);
      setOtp("");
      setStep("otp");
    } else {
      setFormError(result.error);
    }
  };

  /* Step 2 — verify the code. */
  const handleVerify = async (code: string) => {
    clearErrors();
    if (code.length !== OTP_LENGTH) {
      setFieldError("Enter the 6-digit code from your email.");
      return;
    }
    setPending(true);
    const result = await verifyOtp(email, code);
    setPending(false);
    if (result.ok) {
      setResetToken(result.data.resetToken);
      setStep("reset");
    } else {
      // An expired code should be immediately resendable.
      if (result.error.code === "expired-otp") restart(0);
      setFormError(result.error);
    }
  };

  const handleResend = async () => {
    clearErrors();
    setOtp("");
    setPending(true);
    const result = await requestPasswordReset(email);
    setPending(false);
    if (result.ok) {
      restart(result.data.resendAfterSeconds);
    } else {
      setFormError(result.error);
    }
  };

  /* Step 3 — set the new password. */
  const handleReset = async (event: React.FormEvent) => {
    event.preventDefault();
    clearErrors();
    let valid = true;
    if (!isPasswordValid(newPassword)) {
      setFieldError("Password doesn't meet all requirements yet.");
      valid = false;
    }
    if (confirmPassword !== newPassword) {
      setConfirmError("Passwords don't match.");
      valid = false;
    }
    if (!valid) return;
    setPending(true);
    const result = await resetPassword({ resetToken, password: newPassword });
    setPending(false);
    if (result.ok) {
      setStep("success");
    } else {
      setFormError(result.error);
    }
  };

  /* Step 4 — success. */
  if (step === "success") {
    return (
      <AuthCard
        title={copy.success.title}
        description={copy.success.description}
      >
        <div className="flex flex-col items-center gap-6 pt-2">
          <span className="flex size-16 items-center justify-center rounded-full bg-success/10 text-success">
            <CheckCircle2 className="size-8" aria-hidden="true" />
          </span>
          <Button
            className="btn-sheen w-full"
            onClick={() => router.push(siteConfig.app.signIn)}
          >
            {copy.success.cta}
          </Button>
        </div>
      </AuthCard>
    );
  }

  const stepCopy = copy[step];
  const otpInvalid =
    formError?.code === "invalid-otp" || formError?.code === "expired-otp";

  return (
    <AuthCard
      title={stepCopy.title}
      description={
        step === "otp"
          ? `${copy.otp.descriptionPrefix} ${email}.`
          : "description" in stepCopy
            ? stepCopy.description
            : undefined
      }
      footer={
        <>
          {copy.footer.prompt}{" "}
          <Link
            href={siteConfig.app.signIn}
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {copy.footer.linkLabel}
          </Link>
        </>
      }
    >
      {/* Step progress, announced for screen readers. */}
      <p className="sr-only" aria-live="polite">
        Step {step === "email" ? 1 : step === "otp" ? 2 : 3} of 4
      </p>

      {formError ? (
        <Alert
          ref={errorRef}
          variant="destructive"
          tabIndex={-1}
          className="mb-4"
        >
          <AlertCircle className="size-4" aria-hidden="true" />
          <AlertDescription>{formError.message}</AlertDescription>
        </Alert>
      ) : null}

      {step === "email" ? (
        <form onSubmit={handleSendCode} noValidate className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="forgot-email">Email</Label>
            <Input
              id="forgot-email"
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={email}
              disabled={pending}
              aria-invalid={fieldError ? true : undefined}
              aria-describedby={fieldError ? "forgot-email-error" : undefined}
              onChange={(event) => setEmail(event.target.value)}
            />
            {fieldError ? (
              <p id="forgot-email-error" className="text-xs text-destructive">
                {fieldError}
              </p>
            ) : null}
          </div>
          <Button type="submit" className="btn-sheen w-full" disabled={pending}>
            {pending ? (
              <Loader2 className="animate-spin" aria-hidden="true" />
            ) : null}
            {copy.email.cta}
          </Button>
        </form>
      ) : null}

      {step === "otp" ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void handleVerify(otp);
          }}
          noValidate
          className="space-y-5"
        >
          <div className="flex justify-center">
            <span className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <MailCheck className="size-6" aria-hidden="true" />
            </span>
          </div>
          <OtpInput
            length={OTP_LENGTH}
            value={otp}
            invalid={otpInvalid}
            disabled={pending}
            onChange={(value) => {
              setOtp(value);
              if (formError) setFormError(null);
            }}
            onComplete={(value) => void handleVerify(value)}
          />
          {fieldError ? (
            <p className="text-center text-xs text-destructive">{fieldError}</p>
          ) : null}
          <Button
            type="submit"
            className="btn-sheen w-full"
            disabled={pending || otp.length !== OTP_LENGTH}
          >
            {pending ? (
              <Loader2 className="animate-spin" aria-hidden="true" />
            ) : null}
            {copy.otp.cta}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            {remaining > 0 ? (
              <>
                {copy.otp.resendCountdown}{" "}
                <span className="font-mono tabular-nums">{remaining}s</span>
              </>
            ) : (
              <button
                type="button"
                disabled={pending}
                onClick={() => void handleResend()}
                className="font-medium text-primary underline-offset-4 hover:underline disabled:opacity-50"
              >
                {copy.otp.resend}
              </button>
            )}
          </p>
        </form>
      ) : null}

      {step === "reset" ? (
        <form onSubmit={handleReset} noValidate className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="reset-password">New password</Label>
            <PasswordInput
              id="reset-password"
              autoComplete="new-password"
              value={newPassword}
              disabled={pending}
              aria-invalid={fieldError ? true : undefined}
              aria-describedby="reset-password-requirements"
              onChange={(event) => setNewPassword(event.target.value)}
            />
            <div id="reset-password-requirements">
              <PasswordStrength value={newPassword} />
            </div>
            {fieldError ? (
              <p className="text-xs text-destructive">{fieldError}</p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="reset-confirm">Confirm new password</Label>
            <PasswordInput
              id="reset-confirm"
              autoComplete="new-password"
              value={confirmPassword}
              disabled={pending}
              aria-invalid={confirmError ? true : undefined}
              aria-describedby={
                confirmError ? "reset-confirm-error" : undefined
              }
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
            {confirmError ? (
              <p id="reset-confirm-error" className="text-xs text-destructive">
                {confirmError}
              </p>
            ) : null}
          </div>
          <Button type="submit" className="btn-sheen w-full" disabled={pending}>
            {pending ? (
              <Loader2 className="animate-spin" aria-hidden="true" />
            ) : null}
            {copy.reset.cta}
          </Button>
        </form>
      ) : null}
    </AuthCard>
  );
}
