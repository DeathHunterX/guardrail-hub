"use client";

import { Check, X } from "lucide-react";

import { cn, getPasswordStrength, passwordRequirements } from "@/lib/utils";

const meterClasses: Record<number, string> = {
  0: "bg-muted",
  1: "bg-destructive",
  2: "bg-warning",
  3: "bg-primary",
  4: "bg-success",
};

interface PasswordStrengthProps {
  value: string;
  /** Hide the requirement checklist and show only the meter. */
  meterOnly?: boolean;
  className?: string;
}

/** Live strength meter + requirements checklist for password creation. */
export function PasswordStrength({
  value,
  meterOnly = false,
  className,
}: PasswordStrengthProps) {
  const strength = getPasswordStrength(value);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center gap-2">
        <div
          role="meter"
          aria-label="Password strength"
          aria-valuemin={0}
          aria-valuemax={4}
          aria-valuenow={strength.score}
          aria-valuetext={strength.label}
          className="flex flex-1 gap-1"
        >
          {[1, 2, 3, 4].map((step) => (
            <span
              key={step}
              className={cn(
                "h-1 flex-1 rounded-full transition-colors",
                step <= strength.score
                  ? meterClasses[strength.score]
                  : "bg-muted",
              )}
            />
          ))}
        </div>
        {strength.score > 0 ? (
          <span className="w-12 text-right text-xs text-muted-foreground">
            {strength.label}
          </span>
        ) : null}
      </div>

      {meterOnly ? null : (
        <ul className="grid gap-1 sm:grid-cols-2">
          {passwordRequirements.map((rule) => {
            const met = rule.test(value);
            return (
              <li
                key={rule.id}
                className={cn(
                  "flex items-center gap-1.5 text-xs transition-colors",
                  met ? "text-success" : "text-muted-foreground",
                )}
              >
                {met ? (
                  <Check className="size-3 shrink-0" aria-hidden="true" />
                ) : (
                  <X className="size-3 shrink-0" aria-hidden="true" />
                )}
                {rule.label}
                <span className="sr-only">{met ? "— met" : "— not met"}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
