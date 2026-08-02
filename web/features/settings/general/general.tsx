"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { DashboardCard } from "@/components/common/dashboard-card";
import { ErrorState } from "@/components/common/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  getAppPreferences,
  updateAppPreferences,
} from "@/services/settings.service";
import type { ServiceError } from "@/types/api";
import type { AppPreferences } from "@/types/settings";

import { landingPageOptions, upcomingSettings } from "./data";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ServiceError }
  | { status: "ready" };

export function GeneralSettings() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [preferences, setPreferences] = useState<AppPreferences | null>(null);
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState(false);

  // Canonical fetch-in-effect with cancellation; `attempt` re-runs it.
  useEffect(() => {
    let cancelled = false;
    void getAppPreferences().then((result) => {
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

  const patch = (partial: Partial<AppPreferences>) => {
    setSaved(false);
    setPreferences((current) =>
      current ? { ...current, ...partial } : current,
    );
  };

  const handleSave = async () => {
    if (!preferences) return;
    setPending(true);
    const result = await updateAppPreferences(preferences);
    setPending(false);
    if (result.ok) setSaved(true);
  };

  return (
    <>
      <DashboardCard
        title="General"
        description="Defaults for how the app opens and lays out."
      >
        {state.status === "loading" ? (
          <div className="space-y-5" aria-hidden="true">
            <Skeleton className="h-9 w-full max-w-sm" />
            <Skeleton className="h-9 w-64" />
            <Skeleton className="h-6 w-80 max-w-full" />
          </div>
        ) : null}

        {state.status === "error" ? (
          <ErrorState
            description={state.error.message}
            onRetry={retry}
            className="py-6"
          />
        ) : null}

        {state.status === "ready" && preferences ? (
          <div className="space-y-6">
            <div className="max-w-sm space-y-1.5">
              <Label htmlFor="general-landing">Default landing page</Label>
              <Select
                value={preferences.defaultLandingPage}
                onValueChange={(value) =>
                  patch({
                    defaultLandingPage:
                      value as AppPreferences["defaultLandingPage"],
                  })
                }
                disabled={pending}
              >
                <SelectTrigger id="general-landing">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {landingPageOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Where you land right after signing in.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label id="general-density-label">Dashboard density</Label>
              <ToggleGroup
                type="single"
                value={preferences.density}
                onValueChange={(value) => {
                  if (value)
                    patch({ density: value as AppPreferences["density"] });
                }}
                aria-labelledby="general-density-label"
                className="justify-start"
                disabled={pending}
              >
                <ToggleGroupItem value="comfortable">
                  Comfortable
                </ToggleGroupItem>
                <ToggleGroupItem value="compact">Compact</ToggleGroupItem>
              </ToggleGroup>
            </div>

            <div className="flex items-center justify-between gap-4">
              <div>
                <Label htmlFor="general-welcome">Show welcome panel</Label>
                <p className="text-xs text-muted-foreground">
                  Greeting and quick actions at the top of the dashboard.
                </p>
              </div>
              <Switch
                id="general-welcome"
                checked={preferences.showWelcomePanel}
                disabled={pending}
                onCheckedChange={(checked) =>
                  patch({ showWelcomePanel: checked })
                }
              />
            </div>

            <div className="flex items-center gap-3">
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
          </div>
        ) : null}
      </DashboardCard>

      <DashboardCard
        title="More settings on the way"
        description="These areas unlock as their backend services ship."
      >
        <ul className="divide-y">
          {upcomingSettings.map((setting) => (
            <li
              key={setting.title}
              className="flex items-center justify-between gap-4 py-3"
            >
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  {setting.title}
                </p>
                <p className="text-xs text-muted-foreground">
                  {setting.description}
                </p>
              </div>
              <Badge variant="secondary">Soon</Badge>
            </li>
          ))}
        </ul>
      </DashboardCard>
    </>
  );
}
