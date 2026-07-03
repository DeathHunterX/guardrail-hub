"use client";

import { useEffect, useState } from "react";

import { screens, type Screen } from "@/lib/screens";

/**
 * SSR-safe media query hook. Returns `false` on the server and during the
 * first client render, then reflects the live match state.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const mediaQueryList = window.matchMedia(query);
    setMatches(mediaQueryList.matches);

    const onChange = (event: MediaQueryListEvent) => setMatches(event.matches);
    mediaQueryList.addEventListener("change", onChange);
    return () => mediaQueryList.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

/** Convenience wrapper matching Tailwind's min-width breakpoints exactly. */
export function useBreakpoint(screen: Screen): boolean {
  return useMediaQuery(`(min-width: ${screens[screen]}px)`);
}
