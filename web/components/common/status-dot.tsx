import { cn } from "@/lib/utils";

const statusClasses = {
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
  neutral: "bg-muted-foreground",
} as const;

interface StatusDotProps {
  status?: keyof typeof statusClasses;
  /** Adds a CSS pulse halo — disabled automatically under reduced motion. */
  pulse?: boolean;
  className?: string;
}

/** Severity/liveness indicator (spec §0.5). Color is never the only signal — pair with text. */
export function StatusDot({
  status = "neutral",
  pulse = false,
  className,
}: StatusDotProps) {
  return (
    <span
      aria-hidden="true"
      className={cn("relative inline-flex size-2 shrink-0", className)}
    >
      {pulse ? (
        <span
          className={cn(
            "absolute inline-flex size-full rounded-full motion-safe:animate-status-pulse",
            statusClasses[status],
          )}
        />
      ) : null}
      <span
        className={cn(
          "relative inline-flex size-2 rounded-full",
          statusClasses[status],
        )}
      />
    </span>
  );
}
