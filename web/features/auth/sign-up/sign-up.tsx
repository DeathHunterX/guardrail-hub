"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AuthCard } from "@/components/common/auth-card";
import { OAuthButtons } from "@/components/common/oauth-buttons";
import { PasswordInput } from "@/components/common/password-input";
import { PasswordStrength } from "@/components/common/password-strength";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { siteConfig } from "@/config/site";
import { useSession } from "@/hooks/use-session";
import { isPasswordValid, isValidEmail } from "@/lib/utils";
import { signUp, signInWithOAuth } from "@/services/auth.service";
import type { ServiceError } from "@/types/api";
import type { OAuthProvider } from "@/types/auth";

import { signUpCopy } from "./data";

interface FieldErrors {
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
  terms?: string;
}

export function SignUp() {
  const router = useRouter();
  const { startSession } = useSession();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<ServiceError | null>(null);
  const [pending, setPending] = useState(false);
  const [pendingProvider, setPendingProvider] = useState<OAuthProvider | null>(
    null,
  );
  const [succeeded, setSucceeded] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (formError) errorRef.current?.focus();
  }, [formError]);

  const busy = pending || pendingProvider !== null;

  const validate = (): boolean => {
    const errors: FieldErrors = {};
    if (fullName.trim().length < 2) errors.fullName = "Enter your full name.";
    if (!isValidEmail(email)) errors.email = "Enter a valid email address.";
    if (!isPasswordValid(password))
      errors.password = "Password doesn't meet all requirements yet.";
    if (confirmPassword !== password)
      errors.confirmPassword = "Passwords don't match.";
    if (!termsAccepted)
      errors.terms = "You must accept the Terms and Privacy Policy.";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    if (!validate()) return;
    setPending(true);
    const result = await signUp({ fullName: fullName.trim(), email, password });
    setPending(false);
    if (result.ok) {
      startSession(result.data);
      setSucceeded(true);
    } else {
      setFormError(result.error);
    }
  };

  const handleOAuth = async (provider: OAuthProvider) => {
    setFormError(null);
    setPendingProvider(provider);
    const result = await signInWithOAuth(provider);
    setPendingProvider(null);
    if (result.ok) {
      startSession(result.data);
      setSucceeded(true);
    } else {
      setFormError(result.error);
    }
  };

  if (succeeded) {
    return (
      <AuthCard
        title={signUpCopy.success.title}
        description={signUpCopy.success.description}
      >
        <div className="flex flex-col items-center gap-6 pt-2">
          <span className="flex size-16 items-center justify-center rounded-full bg-success/10 text-success">
            <CheckCircle2 className="size-8" aria-hidden="true" />
          </span>
          <Button
            className="btn-sheen w-full"
            onClick={() => router.push(siteConfig.app.dashboard)}
          >
            {signUpCopy.success.cta}
          </Button>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title={signUpCopy.title}
      description={signUpCopy.description}
      footer={
        <>
          {signUpCopy.footer.prompt}{" "}
          <Link
            href={siteConfig.app.signIn}
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {signUpCopy.footer.linkLabel}
          </Link>
        </>
      }
    >
      {formError ? (
        <Alert
          ref={errorRef}
          variant="destructive"
          tabIndex={-1}
          className="mb-4"
        >
          <AlertCircle className="size-4" aria-hidden="true" />
          <AlertDescription>
            {formError.message}
            {formError.code === "email-taken" ? (
              <>
                {" "}
                <Link
                  href={siteConfig.app.signIn}
                  className="font-medium underline underline-offset-4"
                >
                  Sign in
                </Link>
              </>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="signup-name">Full name</Label>
          <Input
            id="signup-name"
            autoComplete="name"
            placeholder="Ada Lovelace"
            value={fullName}
            disabled={busy}
            aria-invalid={fieldErrors.fullName ? true : undefined}
            aria-describedby={
              fieldErrors.fullName ? "signup-name-error" : undefined
            }
            onChange={(event) => setFullName(event.target.value)}
          />
          {fieldErrors.fullName ? (
            <p id="signup-name-error" className="text-xs text-destructive">
              {fieldErrors.fullName}
            </p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="signup-email">Email</Label>
          <Input
            id="signup-email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            value={email}
            disabled={busy}
            aria-invalid={fieldErrors.email ? true : undefined}
            aria-describedby={
              fieldErrors.email ? "signup-email-error" : undefined
            }
            onChange={(event) => setEmail(event.target.value)}
          />
          {fieldErrors.email ? (
            <p id="signup-email-error" className="text-xs text-destructive">
              {fieldErrors.email}
            </p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="signup-password">Password</Label>
          <PasswordInput
            id="signup-password"
            autoComplete="new-password"
            value={password}
            disabled={busy}
            aria-invalid={fieldErrors.password ? true : undefined}
            aria-describedby="signup-password-requirements"
            onChange={(event) => setPassword(event.target.value)}
          />
          <div id="signup-password-requirements">
            <PasswordStrength value={password} />
          </div>
          {fieldErrors.password ? (
            <p className="text-xs text-destructive">{fieldErrors.password}</p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="signup-confirm">Confirm password</Label>
          <PasswordInput
            id="signup-confirm"
            autoComplete="new-password"
            value={confirmPassword}
            disabled={busy}
            aria-invalid={fieldErrors.confirmPassword ? true : undefined}
            aria-describedby={
              fieldErrors.confirmPassword ? "signup-confirm-error" : undefined
            }
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
          {fieldErrors.confirmPassword ? (
            <p id="signup-confirm-error" className="text-xs text-destructive">
              {fieldErrors.confirmPassword}
            </p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-start gap-2">
            <Checkbox
              id="signup-terms"
              checked={termsAccepted}
              disabled={busy}
              aria-invalid={fieldErrors.terms ? true : undefined}
              aria-describedby={
                fieldErrors.terms ? "signup-terms-error" : undefined
              }
              className="mt-0.5"
              onCheckedChange={(checked) => setTermsAccepted(checked === true)}
            />
            <Label htmlFor="signup-terms" className="font-normal leading-snug">
              I agree to the{" "}
              <Link
                href="/terms"
                className="text-primary underline-offset-4 hover:underline"
              >
                Terms of Service
              </Link>{" "}
              and{" "}
              <Link
                href="/privacy"
                className="text-primary underline-offset-4 hover:underline"
              >
                Privacy Policy
              </Link>
              .
            </Label>
          </div>
          {fieldErrors.terms ? (
            <p id="signup-terms-error" className="text-xs text-destructive">
              {fieldErrors.terms}
            </p>
          ) : null}
        </div>

        <Button type="submit" className="btn-sheen w-full" disabled={busy}>
          {pending ? (
            <Loader2 className="animate-spin" aria-hidden="true" />
          ) : null}
          Create account
        </Button>
      </form>

      <div className="my-5 flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="text-xs uppercase tracking-wider text-muted-foreground">
          or
        </span>
        <Separator className="flex-1" />
      </div>

      <OAuthButtons
        intent="up"
        pendingProvider={pendingProvider}
        disabled={pending}
        onSelect={handleOAuth}
      />

      <p className="mt-4 text-center text-xs text-muted-foreground">
        Using enterprise SSO?{" "}
        <Link
          href={siteConfig.app.signIn}
          className="text-primary underline-offset-4 hover:underline"
        >
          Continue with your identity provider
        </Link>
        {" — "}accounts are provisioned on first sign-in.
      </p>
    </AuthCard>
  );
}
