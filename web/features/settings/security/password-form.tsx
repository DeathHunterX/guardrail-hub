"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import { useState } from "react";

import { DashboardCard } from "@/components/common/dashboard-card";
import { PasswordInput } from "@/components/common/password-input";
import { PasswordStrength } from "@/components/common/password-strength";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { isPasswordValid } from "@/lib/utils";
import { changePassword } from "@/services/account.service";
import type { ServiceError } from "@/types/api";

export function PasswordForm() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{
    current?: string;
    next?: string;
    confirm?: string;
  }>({});
  const [error, setError] = useState<ServiceError | null>(null);
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaved(false);
    setError(null);
    const errors: typeof fieldErrors = {};
    if (!currentPassword) errors.current = "Enter your current password.";
    if (!isPasswordValid(newPassword))
      errors.next = "Password doesn't meet all requirements yet.";
    if (confirmPassword !== newPassword)
      errors.confirm = "Passwords don't match.";
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setPending(true);
    const result = await changePassword({ currentPassword, newPassword });
    setPending(false);
    if (result.ok) {
      setSaved(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } else {
      setError(result.error);
    }
  };

  return (
    <DashboardCard
      title="Password"
      description="Use a long, unique password you don't use anywhere else."
    >
      {error ? (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="size-4" aria-hidden="true" />
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      ) : null}

      <form onSubmit={handleSubmit} noValidate className="max-w-md space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="password-current">Current password</Label>
          <PasswordInput
            id="password-current"
            autoComplete="current-password"
            value={currentPassword}
            disabled={pending}
            aria-invalid={fieldErrors.current ? true : undefined}
            aria-describedby={
              fieldErrors.current ? "password-current-error" : undefined
            }
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
          {fieldErrors.current ? (
            <p id="password-current-error" className="text-xs text-destructive">
              {fieldErrors.current}
            </p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password-new">New password</Label>
          <PasswordInput
            id="password-new"
            autoComplete="new-password"
            value={newPassword}
            disabled={pending}
            aria-invalid={fieldErrors.next ? true : undefined}
            aria-describedby="password-new-requirements"
            onChange={(event) => setNewPassword(event.target.value)}
          />
          <div id="password-new-requirements">
            <PasswordStrength value={newPassword} />
          </div>
          {fieldErrors.next ? (
            <p className="text-xs text-destructive">{fieldErrors.next}</p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password-confirm">Confirm new password</Label>
          <PasswordInput
            id="password-confirm"
            autoComplete="new-password"
            value={confirmPassword}
            disabled={pending}
            aria-invalid={fieldErrors.confirm ? true : undefined}
            aria-describedby={
              fieldErrors.confirm ? "password-confirm-error" : undefined
            }
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
          {fieldErrors.confirm ? (
            <p id="password-confirm-error" className="text-xs text-destructive">
              {fieldErrors.confirm}
            </p>
          ) : null}
        </div>

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={pending}>
            {pending ? (
              <Loader2 className="animate-spin" aria-hidden="true" />
            ) : null}
            Update password
          </Button>
          {saved ? (
            <p role="status" className="text-sm text-success">
              Password updated.
            </p>
          ) : null}
        </div>
      </form>
    </DashboardCard>
  );
}
