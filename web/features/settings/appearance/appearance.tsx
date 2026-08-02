"use client";

import { Check, Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { DashboardCard } from "@/components/common/dashboard-card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMounted } from "@/hooks/use-mounted";
import { cn } from "@/lib/utils";

const themeOptions = [
  {
    value: "light",
    label: "Light",
    description: "Bright surfaces, indigo accents.",
    icon: Sun,
  },
  {
    value: "dark",
    label: "Dark",
    description: "Near-black canvas, luminous glows.",
    icon: Moon,
  },
  {
    value: "system",
    label: "System",
    description: "Follows your OS preference.",
    icon: Monitor,
  },
] as const;

export function AppearanceSettings() {
  const { theme, setTheme } = useTheme();
  // Theme is unknown until mounted (next-themes reads it client-side).
  const mounted = useMounted();

  return (
    <DashboardCard
      title="Appearance"
      description="Theme applies instantly across the app."
    >
      {mounted ? (
        <div
          role="radiogroup"
          aria-label="Theme"
          className="grid gap-3 sm:grid-cols-3"
        >
          {themeOptions.map((option) => {
            const selected = theme === option.value;
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setTheme(option.value)}
                className={cn(
                  "rounded-xl border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                  selected
                    ? "border-primary bg-primary/5"
                    : "hover:border-muted-foreground/40",
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="icon-tile size-8 rounded-md">
                    <option.icon className="size-4" aria-hidden="true" />
                  </span>
                  {selected ? (
                    <Check className="size-4 text-primary" aria-hidden="true" />
                  ) : null}
                </div>
                <p className="mt-3 text-sm font-medium">{option.label}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {option.description}
                </p>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-3" aria-hidden="true">
          {themeOptions.map((option) => (
            <Skeleton key={option.value} className="h-28 rounded-xl" />
          ))}
        </div>
      )}
    </DashboardCard>
  );
}
