"use client";

import { ShieldCheck } from "lucide-react";

import { DashboardCard } from "@/components/common/dashboard-card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";

import { PasswordForm } from "./password-form";
import { SessionsCard } from "./sessions-card";

export function SecuritySettings() {
  return (
    <>
      <PasswordForm />

      {/* Placeholder for backend integration: MFA enrollment needs the auth API. */}
      <DashboardCard
        title="Multi-factor authentication"
        description="Add a second factor to protect your account."
        action={<Badge variant="secondary">Soon</Badge>}
      >
        <div className="flex items-center gap-3">
          <span className="icon-tile size-9 rounded-lg">
            <ShieldCheck className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Authenticator app (TOTP)</p>
            <p className="text-xs text-muted-foreground">
              Enrollment opens when MFA ships with the authentication API.
            </p>
          </div>
          <Switch disabled aria-label="Enable multi-factor authentication" />
        </div>
      </DashboardCard>

      <SessionsCard />
    </>
  );
}
