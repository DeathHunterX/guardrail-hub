"use client";

import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { useCallback, useRef } from "react";
import { flushSync } from "react-dom";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useMotion } from "@/providers/gsap-provider";
import { durations } from "@/lib/gsap/motion";
import { useMounted } from "@/hooks/use-mounted";
import { cn } from "@/lib/utils";

type DocumentWithViewTransition = Document & {
  startViewTransition?: (callback: () => void) => { ready: Promise<void> };
};

const THEME_TRANSITION_CLASS = "theme-transitioning";

const themeOptions: Array<{ value: string; label: string; icon: LucideIcon }> = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

interface ThemeToggleProps {
  /**
   * "icon": compact dropdown trigger (header).
   * "segmented": inline three-option control with labels (footer).
   */
  variant?: "icon" | "segmented";
}

/**
 * Theme switcher (spec §0.4). Where the View Transitions API exists, the
 * switch plays a circular reveal from the control; otherwise a scoped 300ms
 * color cross-fade runs. Both paths no-op under reduced motion.
 */
export function ThemeToggle({ variant = "icon" }: ThemeToggleProps) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { tier } = useMotion();
  const mounted = useMounted();
  const controlRef = useRef<HTMLButtonElement>(null);

  const selectTheme = useCallback(
    (next: string) => {
      if (next === theme) return;

      if (tier === "none") {
        setTheme(next);
        return;
      }

      const root = document.documentElement;
      const doc = document as DocumentWithViewTransition;

      // Switching to the identical resolved appearance (e.g. dark -> system
      // while the OS is dark) repaints nothing — skip the theatrics.
      const nextResolved =
        next === "system"
          ? window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light"
          : next;
      if (nextResolved === resolvedTheme) {
        setTheme(next);
        return;
      }

      if (typeof doc.startViewTransition === "function") {
        const rect = controlRef.current?.getBoundingClientRect();
        const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
        const y = rect ? rect.top + rect.height / 2 : 0;
        const radius = Math.hypot(
          Math.max(x, window.innerWidth - x),
          Math.max(y, window.innerHeight - y),
        );

        const transition = doc.startViewTransition(() => {
          flushSync(() => setTheme(next));
        });
        transition.ready
          .then(() => {
            root.animate(
              {
                clipPath: [
                  `circle(0px at ${x}px ${y}px)`,
                  `circle(${radius}px at ${x}px ${y}px)`,
                ],
              },
              {
                duration: durations.md * 1000,
                easing: "ease-in-out",
                pseudoElement: "::view-transition-new(root)",
              },
            );
          })
          .catch(() => {
            // The transition was skipped (rapid toggling) — theme is applied.
          });
        return;
      }

      root.classList.add(THEME_TRANSITION_CLASS);
      setTheme(next);
      window.setTimeout(
        () => root.classList.remove(THEME_TRANSITION_CLASS),
        durations.sm * 1000,
      );
    },
    [theme, resolvedTheme, setTheme, tier],
  );

  if (variant === "segmented") {
    return (
      <div
        role="radiogroup"
        aria-label="Theme"
        className="inline-flex items-center gap-1 rounded-full border bg-card p-1"
      >
        {themeOptions.map((option) => {
          const active = mounted && theme === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={active}
              ref={active ? controlRef : undefined}
              onClick={() => selectTheme(option.value)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <option.icon className="size-3.5" aria-hidden />
              {option.label}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          ref={controlRef}
          variant="ghost"
          size="icon"
          aria-label={mounted ? `Theme: ${resolvedTheme}` : "Theme"}
        >
          <span className="relative flex size-4 items-center justify-center">
            <Sun className="absolute size-4 rotate-0 scale-100 transition-transform duration-300 dark:-rotate-90 dark:scale-0 motion-reduce:transition-none" />
            <Moon className="absolute size-4 rotate-90 scale-0 transition-transform duration-300 dark:rotate-0 dark:scale-100 motion-reduce:transition-none" />
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuRadioGroup
          value={mounted ? theme : undefined}
          onValueChange={selectTheme}
        >
          {themeOptions.map((option) => (
            <DropdownMenuRadioItem key={option.value} value={option.value}>
              <option.icon
                className="mr-2 size-4 text-muted-foreground"
                aria-hidden
              />
              {option.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
