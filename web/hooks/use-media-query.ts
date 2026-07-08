"use client";

import { useCallback, useSyncExternalStore } from "react";

import { screens, type Screen } from "@/lib/screens";

function getServerSnapshot(): boolean {
  return false;
}

/**
 * SSR-safe media query hook. Returns `false` on the server and during the
 * first client render, then reflects the live match state.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mediaQueryList = window.matchMedia(query);
      mediaQueryList.addEventListener("change", onChange);
      return () => mediaQueryList.removeEventListener("change", onChange);
    },
    [query],
  );

  const getSnapshot = useCallback(() => window.matchMedia(query).matches, [query]);

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/** Convenience wrapper matching Tailwind's min-width breakpoints exactly. */
export function useBreakpoint(screen: Screen): boolean {
  return useMediaQuery(`(min-width: ${screens[screen]}px)`);
}
