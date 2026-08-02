"use client";

import { useEffect, useState } from "react";

import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { DashboardCard } from "@/components/common/dashboard-card";
import { ErrorState } from "@/components/common/error-state";
import { oauthProviders } from "@/components/common/oauth-buttons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  connectAccount,
  disconnectAccount,
  getConnectedAccounts,
} from "@/services/account.service";
import type { ServiceError } from "@/types/api";
import type { ConnectedAccount, OAuthProvider } from "@/types/auth";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ServiceError }
  | { status: "ready"; accounts: ConnectedAccount[] };

export function ConnectedAccountsSettings() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [busyProvider, setBusyProvider] = useState<OAuthProvider | null>(null);
  const [disconnectTarget, setDisconnectTarget] =
    useState<ConnectedAccount | null>(null);

  // Canonical fetch-in-effect with cancellation; `attempt` re-runs it.
  useEffect(() => {
    let cancelled = false;
    void getConnectedAccounts().then((result) => {
      if (cancelled) return;
      setState(
        result.ok
          ? { status: "ready", accounts: result.data }
          : { status: "error", error: result.error },
      );
    });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = () => {
    setState({ status: "loading" });
    setAttempt((current) => current + 1);
  };

  const patchAccount = (next: ConnectedAccount) => {
    setState((current) =>
      current.status === "ready"
        ? {
            status: "ready",
            accounts: current.accounts.map((account) =>
              account.provider === next.provider ? next : account,
            ),
          }
        : current,
    );
  };

  const handleConnect = async (provider: OAuthProvider) => {
    setBusyProvider(provider);
    const result = await connectAccount(provider);
    setBusyProvider(null);
    if (result.ok) patchAccount(result.data);
  };

  const handleDisconnect = async () => {
    if (!disconnectTarget) return;
    setBusyProvider(disconnectTarget.provider);
    const result = await disconnectAccount(disconnectTarget.provider);
    setBusyProvider(null);
    if (result.ok) {
      patchAccount({
        provider: disconnectTarget.provider,
        email: "",
        connectedAt: null,
      });
    }
    setDisconnectTarget(null);
  };

  return (
    <DashboardCard
      title="Connected accounts"
      description="Sign in with these providers alongside your email."
    >
      {state.status === "loading" ? (
        <div className="space-y-3" aria-hidden="true">
          {Array.from({ length: 3 }, (_, index) => (
            <div key={index} className="flex items-center gap-3">
              <Skeleton className="size-9 rounded-lg" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-3 w-44" />
              </div>
              <Skeleton className="h-8 w-24" />
            </div>
          ))}
        </div>
      ) : null}

      {state.status === "error" ? (
        <ErrorState
          description={state.error.message}
          onRetry={retry}
          className="py-6"
        />
      ) : null}

      {state.status === "ready" ? (
        <ul className="divide-y">
          {oauthProviders.map(({ id, label, icon: Icon }) => {
            const account = state.accounts.find(
              (entry) => entry.provider === id,
            );
            const connected = Boolean(account?.connectedAt);
            const busy = busyProvider === id;
            return (
              <li key={id} className="flex items-center gap-3 py-3">
                <span className="flex size-9 items-center justify-center rounded-lg border bg-background [&_svg]:size-4">
                  <Icon />
                </span>
                <div className="min-w-0 flex-1">
                  {/* span, not p: Badge renders a <div>, invalid inside <p> */}
                  <span className="flex items-center gap-2 text-sm font-medium">
                    {label}
                    {connected ? (
                      <Badge variant="success" className="px-1.5 text-[10px]">
                        Connected
                      </Badge>
                    ) : null}
                  </span>
                  <p className="truncate text-xs text-muted-foreground">
                    {connected
                      ? account?.email
                      : `Link your ${label} account for one-click sign-in.`}
                  </p>
                </div>
                {connected ? (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() => account && setDisconnectTarget(account)}
                  >
                    Disconnect
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() => void handleConnect(id)}
                  >
                    {busy ? "Connecting…" : "Connect"}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}

      <ConfirmationDialog
        open={disconnectTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDisconnectTarget(null);
        }}
        title="Disconnect account?"
        description={
          disconnectTarget
            ? `You'll no longer be able to sign in with ${oauthProviders.find((p) => p.id === disconnectTarget.provider)?.label} (${disconnectTarget.email}).`
            : ""
        }
        confirmLabel="Disconnect"
        destructive
        pending={busyProvider !== null}
        onConfirm={() => void handleDisconnect()}
      />
    </DashboardCard>
  );
}
