"use client";

import { ArrowRight, Sparkles, X } from "lucide-react";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { announcement } from "@/content/site";
import { useMotion } from "@/lib/gsap/gsap-provider";
import { durations, eases } from "@/lib/gsap/motion";
import { gsap, useGSAP } from "@/lib/gsap/register";
import { useLocalStorage } from "@/lib/hooks/use-local-storage";

/**
 * Announcement bar (spec §1). SSR renders the bar for everyone (most
 * visitors have not dismissed it); the persisted dismissal removes it after
 * hydration without animation. Live dismissal collapses the bar, then
 * persists.
 */
export function AnnouncementBar() {
  const [dismissed, setDismissed, hydrated] = useLocalStorage(
    `announcement:${announcement.id}`,
    false,
  );
  const { tier, requestRefresh } = useMotion();
  const barRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (tier === "none" || !barRef.current) return;
      gsap.from(barRef.current, {
        yPercent: -100,
        autoAlpha: 0,
        duration: durations.sm,
        ease: eases.enter,
      });
    },
    { scope: barRef, dependencies: [tier] },
  );

  const dismiss = () => {
    const element = barRef.current;
    if (tier === "none" || !element) {
      setDismissed(true);
      requestRefresh();
      return;
    }
    // One-off height collapse on a 40px element — the sanctioned exception
    // to the transforms-only rule (architecture §11).
    gsap.to(element, {
      height: 0,
      autoAlpha: 0,
      duration: durations.sm,
      ease: eases.morph,
      onComplete: () => {
        setDismissed(true);
        requestRefresh();
      },
    });
  };

  if (hydrated && dismissed) return null;

  return (
    <div
      ref={barRef}
      role="region"
      aria-label="Announcement"
      className="relative isolate flex h-10 items-center justify-center gap-2.5 overflow-hidden border-b bg-primary/5 px-12 text-sm dark:bg-primary/10"
    >
      <Sparkles className="size-3.5 shrink-0 text-primary" aria-hidden />
      <p className="truncate">
        <span className="hidden sm:inline">{announcement.message}</span>
        <span className="sm:hidden">{announcement.shortMessage}</span>{" "}
        <a
          href={announcement.href}
          target="_blank"
          rel="noreferrer"
          className="group inline-flex items-center gap-1 font-medium"
        >
          <span className="bg-brand-gradient bg-[length:200%_auto] bg-clip-text text-transparent motion-safe:animate-shimmer">
            {announcement.linkLabel}
          </span>
          <ArrowRight
            className="size-3.5 text-primary transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none"
            aria-hidden
          />
        </a>
      </p>
      <Button
        variant="ghost"
        size="icon"
        onClick={dismiss}
        aria-label="Dismiss announcement"
        className="absolute right-1 top-1/2 h-10 w-10 -translate-y-1/2 sm:h-8 sm:w-8"
      >
        <X aria-hidden />
      </Button>
    </div>
  );
}
