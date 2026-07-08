"use client";

import { useCallback, useRef, useSyncExternalStore } from "react";

import { ScrollTrigger } from "@/lib/gsap/register";

const SCROLL_THRESHOLD_PX = 24;

function getServerSnapshot(): boolean {
  return false;
}

/**
 * Scrolled-state detection for the sticky header (spec §2). This is state
 * detection, not motion, so it runs in every motion tier — the glass
 * treatment must appear for reduced-motion users too.
 */
export function useHeaderScroll(): boolean {
  const activeRef = useRef(false);

  const subscribe = useCallback((onChange: () => void) => {
    const trigger = ScrollTrigger.create({
      start: SCROLL_THRESHOLD_PX,
      end: "max",
      onToggle: (self) => {
        activeRef.current = self.isActive;
        onChange();
      },
    });
    // Catches the case where the page loads already scrolled past the
    // threshold (e.g. restored scroll position on back-navigation).
    activeRef.current = trigger.isActive;
    onChange();
    return () => trigger.kill();
  }, []);

  const getSnapshot = useCallback(() => activeRef.current, []);

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
