"use client";

import { AlertCircle, Building2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AuthCard } from "@/components/common/auth-card";
import { OAuthButtons } from "@/components/common/oauth-buttons";
import { PasswordInput } from "@/components/common/password-input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { siteConfig } from "@/config/site";
import { useSession } from "@/hooks/use-session";
import { isValidEmail } from "@/lib/utils";
import {
  signIn,
  signInWithEnterprise,
  signInWithOAuth,
} from "@/services/auth.service";
import type { ServiceError } from "@/types/api";
import type { EnterpriseProtocol, OAuthProvider } from "@/types/auth";

import { signInCopy } from "./data";

type Mode = "credentials" | "enterprise";

interface FieldErrors {
  email?: string;
  password?: string;
}

export function SignIn() {
  const router = useRouter();
  const { session, hydrated, startSession } = useSession();

  const [mode, setMode] = useState<Mode>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [protocol, setProtocol] = useState<EnterpriseProtocol>("oidc");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<ServiceError | null>(null);
  const [pending, setPending] = useState(false);
  const [pendingProvider, setPendingProvider] = useState<OAuthProvider | null>(
    null,
  );
  const errorRef = useRef<HTMLDivElement>(null);

  // Already signed in — go straight to the app.
  useEffect(() => {
    if (hydrated && session) router.replace(siteConfig.app.dashboard);
  }, [hydrated, session, router]);

  // Move screen-reader/keyboard focus to fresh submit errors.
  useEffect(() => {
    if (formError) errorRef.current?.focus();
  }, [formError]);

  const busy = pending || pendingProvider !== null;

  const validate = (): boolean => {
    const errors: FieldErrors = {};
    if (!isValidEmail(email)) errors.email = "Enter a valid email address.";
    if (mode === "credentials" && !password)
      errors.password = "Enter your password.";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const finish = (result: Awaited<ReturnType<typeof signIn>>) => {
    if (result.ok) {
      startSession(result.data);
      router.push(siteConfig.app.dashboard);
    } else {
      setFormError(result.error);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    if (!validate()) return;
    setPending(true);
    const result =
      mode === "credentials"
        ? await signIn({ email, password, rememberMe })
        : await signInWithEnterprise({ email, protocol });
    setPending(false);
    finish(result);
  };

  const handleOAuth = async (provider: OAuthProvider) => {
    setFormError(null);
    setPendingProvider(provider);
    const result = await signInWithOAuth(provider);
    setPendingProvider(null);
    finish(result);
  };

  const enterprise = mode === "enterprise";

  return (
    <AuthCard
      title={enterprise ? signInCopy.enterprise.title : signInCopy.title}
      description={
        enterprise ? signInCopy.enterprise.description : signInCopy.description
      }
      footer={
        <>
          {signInCopy.footer.prompt}{" "}
          <Link
            href={siteConfig.app.signUp}
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {signInCopy.footer.linkLabel}
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
          <AlertDescription>{formError.message}</AlertDescription>
        </Alert>
      ) : null}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="signin-email">
            {enterprise ? "Work email" : "Email"}
          </Label>
          <Input
            id="signin-email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            value={email}
            disabled={busy}
            aria-invalid={fieldErrors.email ? true : undefined}
            aria-describedby={
              fieldErrors.email ? "signin-email-error" : undefined
            }
            onChange={(event) => setEmail(event.target.value)}
          />
          {fieldErrors.email ? (
            <p id="signin-email-error" className="text-xs text-destructive">
              {fieldErrors.email}
            </p>
          ) : null}
        </div>

        {enterprise ? (
          <div className="space-y-1.5">
            <Label htmlFor="signin-protocol">Identity protocol</Label>
            <Select
              value={protocol}
              onValueChange={(value) =>
                setProtocol(value as EnterpriseProtocol)
              }
              disabled={busy}
            >
              <SelectTrigger id="signin-protocol">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="oidc">OpenID Connect (OIDC)</SelectItem>
                <SelectItem value="saml">SAML 2.0</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {signInCopy.enterprise.note}
            </p>
          </div>
        ) : (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="signin-password">Password</Label>
              <Link
                href={siteConfig.app.forgotPassword}
                className="text-xs text-primary underline-offset-4 hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <PasswordInput
              id="signin-password"
              autoComplete="current-password"
              value={password}
              disabled={busy}
              aria-invalid={fieldErrors.password ? true : undefined}
              aria-describedby={
                fieldErrors.password ? "signin-password-error" : undefined
              }
              onChange={(event) => setPassword(event.target.value)}
            />
            {fieldErrors.password ? (
              <p
                id="signin-password-error"
                className="text-xs text-destructive"
              >
                {fieldErrors.password}
              </p>
            ) : null}
          </div>
        )}

        {enterprise ? null : (
          <div className="flex items-center gap-2">
            <Checkbox
              id="signin-remember"
              checked={rememberMe}
              disabled={busy}
              onCheckedChange={(checked) => setRememberMe(checked === true)}
            />
            <Label htmlFor="signin-remember" className="font-normal">
              Remember me
            </Label>
          </div>
        )}

        <Button type="submit" className="btn-sheen w-full" disabled={busy}>
          {pending ? (
            <Loader2 className="animate-spin" aria-hidden="true" />
          ) : null}
          {enterprise ? "Continue with SSO" : "Sign in"}
        </Button>
      </form>

      <div className="my-5 flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="text-xs uppercase tracking-wider text-muted-foreground">
          or
        </span>
        <Separator className="flex-1" />
      </div>

      {enterprise ? null : (
        <OAuthButtons
          pendingProvider={pendingProvider}
          disabled={pending}
          onSelect={handleOAuth}
        />
      )}

      <Button
        type="button"
        variant={enterprise ? "outline" : "ghost"}
        className="mt-2 w-full"
        disabled={busy}
        onClick={() => {
          setMode(enterprise ? "credentials" : "enterprise");
          setFormError(null);
          setFieldErrors({});
        }}
      >
        <Building2 aria-hidden="true" />
        {enterprise ? "Back to email sign-in" : "Continue with Enterprise SSO"}
      </Button>
    </AuthCard>
  );
}
