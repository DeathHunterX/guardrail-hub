import { ArrowRight, ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CTALink {
  label: string;
  href: string;
  external?: boolean;
}

interface CTAGroupProps {
  primary: CTALink;
  secondary?: CTALink;
  /** Quiet text links rendered under the buttons (docs, GitHub). */
  tertiary?: CTALink[];
  size?: "default" | "xl";
  /** "onGradient" restyles the pair for the final CTA's gradient panel. */
  tone?: "default" | "onGradient";
  align?: "start" | "center";
  className?: string;
}

/**
 * Canonical CTA arrangement (spec: hero, pricing, final CTA). Centralizing it
 * guarantees consistent sizing, iconography, and sheen treatment page-wide.
 */
export function CTAGroup({
  primary,
  secondary,
  tertiary,
  size = "default",
  tone = "default",
  align = "start",
  className,
}: CTAGroupProps) {
  const centered = align === "center";
  const buttonSize = size === "xl" ? "xl" : "lg";

  return (
    <div className={cn(centered && "text-center", className)}>
      <div
        className={cn(
          "flex flex-col gap-3 sm:flex-row",
          centered && "sm:justify-center",
        )}
      >
        <Button
          asChild
          size={buttonSize}
          variant={tone === "onGradient" ? "secondary" : "default"}
          className={cn("btn-sheen", tone === "onGradient" && "shadow-lg")}
        >
          <Link href={primary.href}>
            {primary.label}
            <ArrowRight aria-hidden />
          </Link>
        </Button>
        {secondary ? (
          <Button
            asChild
            size={buttonSize}
            variant="outline"
            className={cn(
              tone === "onGradient" &&
                "border-white/40 bg-transparent text-white hover:bg-white/10 hover:text-white",
            )}
          >
            <Link href={secondary.href}>{secondary.label}</Link>
          </Button>
        ) : null}
      </div>
      {tertiary && tertiary.length > 0 ? (
        <div
          className={cn(
            "mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm",
            centered && "justify-center",
          )}
        >
          {tertiary.map((link) => (
            <a
              key={link.label}
              href={link.href}
              {...(link.external
                ? { target: "_blank", rel: "noreferrer" }
                : {})}
              className="group inline-flex items-center gap-1 text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
              <ArrowUpRight
                className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none"
                aria-hidden
              />
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}
