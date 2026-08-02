import type { LucideIcon } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type MetricTone = "default" | "success" | "warning" | "destructive";

const deltaToneClasses: Record<MetricTone, string> = {
  default: "text-muted-foreground",
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
};

interface MetricCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  /** Short trend/context line, e.g. "+12% vs last week". */
  delta?: string;
  deltaTone?: MetricTone;
  className?: string;
}

/** KPI stat card for dashboard grids — icon tile, mono value, trend line. */
export function MetricCard({
  label,
  value,
  icon: Icon,
  delta,
  deltaTone = "default",
  className,
}: MetricCardProps) {
  return (
    <Card className={cn("flex items-start gap-4 p-5", className)}>
      <span className="icon-tile">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm text-muted-foreground">{label}</p>
        <p className="mt-1 font-mono text-2xl font-semibold tabular-nums tracking-tight">
          {value}
        </p>
        {delta ? (
          <p className={cn("mt-0.5 text-xs", deltaToneClasses[deltaTone])}>
            {delta}
          </p>
        ) : null}
      </div>
    </Card>
  );
}

/** Loading placeholder matching MetricCard's layout exactly. */
export function MetricCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("flex items-start gap-4 p-5", className)}>
      <Skeleton className="size-10 shrink-0 rounded-lg" />
      <div className="w-full space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-7 w-16" />
        <Skeleton className="h-3 w-20" />
      </div>
    </Card>
  );
}
