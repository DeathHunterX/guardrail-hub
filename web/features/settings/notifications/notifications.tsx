"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { DashboardCard } from "@/components/common/dashboard-card";
import { ErrorState } from "@/components/common/error-state";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  getNotificationPreferences,
  updateNotificationPreferences,
} from "@/services/settings.service";
import type { ServiceError } from "@/types/api";
import type { NotificationPreferences } from "@/types/settings";

import { appPreferenceItems, emailPreferenceItems } from "./data";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ServiceError }
  | { status: "ready" };

function ToggleListSkeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-4" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex items-center justify-between gap-4">
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-3 w-64 max-w-full" />
          </div>
          <Skeleton className="h-5 w-9 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function NotificationsSettings() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [preferences, setPreferences] =
    useState<NotificationPreferences | null>(null);
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState(false);

  // Canonical fetch-in-effect with cancellation; `attempt` re-runs it.
  useEffect(() => {
    let cancelled = false;
    void getNotificationPreferences().then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setPreferences(result.data);
        setState({ status: "ready" });
      } else {
        setState({ status: "error", error: result.error });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = () => {
    setState({ status: "loading" });
    setAttempt((current) => current + 1);
  };

  const toggleEmail = (
    key: keyof NotificationPreferences["email"],
    value: boolean,
  ) => {
    setSaved(false);
    setPreferences((current) =>
      current
        ? { ...current, email: { ...current.email, [key]: value } }
        : current,
    );
  };

  const toggleApp = (
    key: keyof NotificationPreferences["inApp"],
    value: boolean,
  ) => {
    setSaved(false);
    setPreferences((current) =>
      current
        ? { ...current, inApp: { ...current.inApp, [key]: value } }
        : current,
    );
  };

  const handleSave = async () => {
    if (!preferences) return;
    setPending(true);
    const result = await updateNotificationPreferences(preferences);
    setPending(false);
    if (result.ok) setSaved(true);
  };

  if (state.status === "error") {
    return (
      <DashboardCard title="Notifications" description="">
        <ErrorState
          description={state.error.message}
          onRetry={retry}
          className="py-6"
        />
      </DashboardCard>
    );
  }

  const ready = state.status === "ready" && preferences;

  return (
    <>
      <DashboardCard
        title="Email notifications"
        description="What lands in your inbox."
      >
        {ready ? (
          <div className="space-y-4">
            {emailPreferenceItems.map((item) => (
              <div
                key={item.key}
                className="flex items-center justify-between gap-4"
              >
                <div>
                  <Label htmlFor={`email-${item.key}`}>{item.label}</Label>
                  <p className="text-xs text-muted-foreground">
                    {item.description}
                  </p>
                </div>
                <Switch
                  id={`email-${item.key}`}
                  checked={preferences.email[item.key]}
                  disabled={pending}
                  onCheckedChange={(checked) => toggleEmail(item.key, checked)}
                />
              </div>
            ))}
          </div>
        ) : (
          <ToggleListSkeleton rows={4} />
        )}
      </DashboardCard>

      <DashboardCard
        title="In-app notifications"
        description="What appears in the notification bell."
      >
        {ready ? (
          <div className="space-y-4">
            {appPreferenceItems.map((item) => (
              <div
                key={item.key}
                className="flex items-center justify-between gap-4"
              >
                <div>
                  <Label htmlFor={`inapp-${item.key}`}>{item.label}</Label>
                  <p className="text-xs text-muted-foreground">
                    {item.description}
                  </p>
                </div>
                <Switch
                  id={`inapp-${item.key}`}
                  checked={preferences.inApp[item.key]}
                  disabled={pending}
                  onCheckedChange={(checked) => toggleApp(item.key, checked)}
                />
              </div>
            ))}
          </div>
        ) : (
          <ToggleListSkeleton rows={3} />
        )}

        {ready ? (
          <div className="mt-6 flex items-center gap-3">
            <Button
              type="button"
              disabled={pending}
              onClick={() => void handleSave()}
            >
              {pending ? (
                <Loader2 className="animate-spin" aria-hidden="true" />
              ) : null}
              Save changes
            </Button>
            {saved ? (
              <p role="status" className="text-sm text-success">
                Changes saved.
              </p>
            ) : null}
          </div>
        ) : null}
      </DashboardCard>
    </>
  );
}
