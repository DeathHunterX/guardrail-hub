"use client";

import { Laptop, MonitorSmartphone, Smartphone } from "lucide-react";
import { useEffect, useState } from "react";

import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { DashboardCard } from "@/components/common/dashboard-card";
import { ErrorState } from "@/components/common/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelativeTime } from "@/lib/utils";
import { getActiveSessions, revokeSession } from "@/services/account.service";
import type { ServiceError } from "@/types/api";
import type { ActiveSession } from "@/types/auth";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ServiceError }
  | { status: "ready"; sessions: ActiveSession[] };

function deviceIcon(device: string) {
  if (/iphone|android|pixel/i.test(device)) return Smartphone;
  if (/macbook|laptop/i.test(device)) return Laptop;
  return MonitorSmartphone;
}

/** Active sessions & connected devices list with revoke-on-confirm. */
export function SessionsCard() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [revokeTarget, setRevokeTarget] = useState<ActiveSession | null>(null);
  const [revoking, setRevoking] = useState(false);

  // Canonical fetch-in-effect with cancellation; `attempt` re-runs it.
  useEffect(() => {
    let cancelled = false;
    void getActiveSessions().then((result) => {
      if (cancelled) return;
      setState(
        result.ok
          ? { status: "ready", sessions: result.data }
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

  const handleRevoke = async () => {
    if (!revokeTarget || state.status !== "ready") return;
    setRevoking(true);
    const result = await revokeSession(revokeTarget.id);
    setRevoking(false);
    if (result.ok) {
      setState({
        status: "ready",
        sessions: state.sessions.filter(
          (session) => session.id !== revokeTarget.id,
        ),
      });
    }
    setRevokeTarget(null);
  };

  return (
    <DashboardCard
      title="Active sessions"
      description="Devices currently signed in to your account."
    >
      {state.status === "loading" ? (
        <div className="space-y-3" aria-hidden="true">
          {Array.from({ length: 3 }, (_, index) => (
            <div key={index} className="flex items-center gap-3">
              <Skeleton className="size-9 rounded-lg" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-56" />
              </div>
              <Skeleton className="h-8 w-16" />
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
          {state.sessions.map((session) => {
            const Icon = deviceIcon(session.device);
            return (
              <li key={session.id} className="flex items-center gap-3 py-3">
                <span className="icon-tile size-9 rounded-lg">
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  {/* span, not p: Badge renders a <div>, invalid inside <p> */}
                  <span className="flex items-center gap-2 text-sm font-medium">
                    <span className="truncate">{session.device}</span>
                    {session.current ? (
                      <Badge variant="success" className="px-1.5 text-[10px]">
                        This device
                      </Badge>
                    ) : null}
                  </span>
                  <p className="truncate text-xs text-muted-foreground">
                    {session.browser} · {session.location} ·{" "}
                    {formatRelativeTime(session.lastActiveAt)}
                  </p>
                </div>
                {session.current ? null : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setRevokeTarget(session)}
                  >
                    Revoke
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}

      <ConfirmationDialog
        open={revokeTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRevokeTarget(null);
        }}
        title="Revoke session?"
        description={
          revokeTarget
            ? `${revokeTarget.device} (${revokeTarget.location}) will be signed out immediately.`
            : ""
        }
        confirmLabel="Revoke session"
        destructive
        pending={revoking}
        onConfirm={() => void handleRevoke()}
      />
    </DashboardCard>
  );
}
