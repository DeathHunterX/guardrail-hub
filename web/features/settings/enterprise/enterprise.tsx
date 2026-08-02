"use client";

import { GlobeLock } from "lucide-react";

import { DashboardCard } from "@/components/common/dashboard-card";
import { EmptyState } from "@/components/common/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { externalLinks } from "@/constants/external-links";
import { useSession } from "@/hooks/use-session";

export function EnterpriseSettings() {
  const { session } = useSession();
  const enterprise = session?.user.enterprise ?? null;

  return (
    <DashboardCard
      title="Enterprise identity"
      description="How your account is governed by your organization's identity provider."
    >
      {enterprise ? (
        <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-muted-foreground">Identity provider</dt>
            <dd className="mt-1 text-sm font-medium">{enterprise.provider}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Protocol</dt>
            <dd className="mt-1">
              <Badge
                variant="secondary"
                className="font-mono text-[10px] uppercase"
              >
                {enterprise.protocol}
              </Badge>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Verified domain</dt>
            <dd className="mt-1 font-mono text-sm">{enterprise.domain}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Session policy</dt>
            <dd className="mt-1 text-sm text-muted-foreground">
              Managed by your identity provider — password and MFA settings are
              controlled there.
            </dd>
          </div>
        </dl>
      ) : (
        <EmptyState
          icon={GlobeLock}
          title="No enterprise identity linked"
          description="Your account uses individual sign-in. When your organization enables SSO (OIDC or SAML 2.0), enterprise details appear here."
          action={
            <Button variant="outline" size="sm" asChild>
              <a href={externalLinks.docs} target="_blank" rel="noreferrer">
                SSO setup guide
              </a>
            </Button>
          }
          className="py-8"
        />
      )}
    </DashboardCard>
  );
}
