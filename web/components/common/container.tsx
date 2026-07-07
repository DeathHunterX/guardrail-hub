import type { ElementType, ReactNode } from "react";

import { cn } from "@/lib/utils";

const sizeClasses = {
  default: "max-w-7xl",
  narrow: "max-w-4xl",
  wide: "max-w-[88rem]",
} as const;

interface ContainerProps {
  size?: keyof typeof sizeClasses;
  /** Rendered element — defaults to a plain div. */
  as?: ElementType;
  className?: string;
  children: ReactNode;
}

/** Horizontal page rhythm (spec §0.3). Used by every section and the chrome. */
export function Container({
  size = "default",
  as: Component = "div",
  className,
  children,
}: ContainerProps) {
  return (
    <Component
      className={cn("mx-auto px-4 sm:px-6 md:px-8", sizeClasses[size], className)}
    >
      {children}
    </Component>
  );
}
