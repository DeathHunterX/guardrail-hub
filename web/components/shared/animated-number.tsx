"use client";

import { useRef } from "react";

import { useMotion } from "@/lib/gsap/gsap-provider";
import { durations, eases } from "@/lib/gsap/motion";
import { gsap, useGSAP } from "@/lib/gsap/register";
import { cn, formatCompactNumber } from "@/lib/utils";

type FormatStyle = "grouped" | "compact" | "one-decimal";

interface AnimatedNumberProps {
  value: number;
  /**
   * Serializable formatter selector — safe to pass from server components.
   * Client callers may pass `format` instead; it takes precedence.
   */
  formatStyle?: FormatStyle;
  format?: (value: number) => string;
  /** Tween duration in seconds — must come from motion tokens. */
  duration?: number;
  /** "inView" (default) counts up on scroll into view; "mount" immediately. */
  trigger?: "mount" | "inView";
  className?: string;
}

const formatters: Record<FormatStyle, (value: number) => string> = {
  grouped: (value) => Math.round(value).toLocaleString("en-US"),
  compact: formatCompactNumber,
  "one-decimal": (value) => value.toFixed(1),
};

/**
 * GSAP counter (shared primitive, spec §0.5). SSR renders the final value so
 * SEO, find-in-page, and the reduced-motion tier are correct by default.
 * Subsequent `value` changes tween from the previously displayed number
 * (pricing toggle behavior) rather than restarting at zero.
 */
export function AnimatedNumber({
  value,
  formatStyle = "grouped",
  format,
  duration = durations.lg,
  trigger = "inView",
  className,
}: AnimatedNumberProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const displayed = useRef(0);
  const { tier } = useMotion();
  const fmt = format ?? formatters[formatStyle];

  useGSAP(
    () => {
      const element = ref.current;
      if (!element) return;

      if (tier === "none") {
        element.textContent = fmt(value);
        displayed.current = value;
        return;
      }

      const proxy = { current: displayed.current };
      gsap.to(proxy, {
        current: value,
        duration,
        ease: eases.enter,
        snap: Number.isInteger(value) ? { current: 1 } : undefined,
        onUpdate: () => {
          element.textContent = fmt(proxy.current);
          displayed.current = proxy.current;
        },
        ...(trigger === "inView"
          ? {
              scrollTrigger: {
                trigger: element,
                start: "top 90%",
                once: true,
              },
            }
          : {}),
      });
    },
    { dependencies: [tier, value], revertOnUpdate: true },
  );

  return (
    <span ref={ref} className={cn("tabular-nums", className)}>
      {fmt(value)}
    </span>
  );
}
