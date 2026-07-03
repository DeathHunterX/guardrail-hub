"use client";

import { useEffect, useState } from "react";

import { ScrollTrigger } from "@/lib/gsap/register";

const SCROLL_THRESHOLD_PX = 24;

/**
 * Scrolled-state detection for the sticky header (spec §2). This is state
 * detection, not motion, so it runs in every motion tier — the glass
 * treatment must appear for reduced-motion users too.
 */
export function useHeaderScroll(): boolean {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const trigger = ScrollTrigger.create({
      start: SCROLL_THRESHOLD_PX,
      end: "max",
      onToggle: (self) => setScrolled(self.isActive),
    });
    setScrolled(trigger.isActive);
    return () => trigger.kill();
  }, []);

  return scrolled;
}
