"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { gsap, ScrollTrigger } from "@/lib/gsap/register";

/**
 * Motion tiers (architecture §11 degradation matrix):
 * - "full":    >= lg viewport, motion allowed — pins, scrubs, particles, loops.
 * - "compact": < lg viewport, motion allowed — no pins, simplified timelines.
 * - "none":    prefers-reduced-motion — static final states, opacity-only fades.
 *
 * SSR renders with "none" so reduced-motion users never see a flash of motion.
 * On the client the tier is resolved synchronously in the state initializer:
 * child effects (entrance timelines) run before this provider's own effect,
 * so they must be able to read the real tier on their very first pass.
 */
export type MotionTier = "none" | "compact" | "full";

function resolveTier(): MotionTier {
  if (typeof window === "undefined") return "none";
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return "none";
  }
  return window.matchMedia("(min-width: 1024px)").matches ? "full" : "compact";
}

interface MotionContextValue {
  tier: MotionTier;
  /** True once the chrome (announcement bar + header) entrance has settled. */
  entranceDone: boolean;
  /** Called by the site header when its load animation completes. */
  signalEntranceDone: () => void;
  /** Debounced ScrollTrigger.refresh() for post-load layout shifts. */
  requestRefresh: () => void;
}

const MotionContext = createContext<MotionContextValue | null>(null);

export function GsapProvider({ children }: { children: ReactNode }) {
  const [tier, setTier] = useState<MotionTier>(resolveTier);
  const [entranceDone, setEntranceDone] = useState(false);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    ScrollTrigger.config({ ignoreMobileResize: true });

    const mm = gsap.matchMedia();
    mm.add(
      {
        reduce: "(prefers-reduced-motion: reduce)",
        desktop: "(min-width: 1024px)",
      },
      (context) => {
        const { reduce, desktop } = context.conditions as {
          reduce: boolean;
          desktop: boolean;
        };
        setTier(reduce ? "none" : desktop ? "full" : "compact");
      },
    );

    return () => mm.revert();
  }, []);

  const signalEntranceDone = useCallback(() => setEntranceDone(true), []);

  const requestRefresh = useCallback(() => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(() => ScrollTrigger.refresh(), 200);
  }, []);

  useEffect(() => {
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, []);

  const value = useMemo(
    () => ({ tier, entranceDone, signalEntranceDone, requestRefresh }),
    [tier, entranceDone, signalEntranceDone, requestRefresh],
  );

  return (
    <MotionContext.Provider value={value}>{children}</MotionContext.Provider>
  );
}

/** Accessor for the motion context. Throws when used outside the provider. */
export function useMotion(): MotionContextValue {
  const context = useContext(MotionContext);
  if (!context) {
    throw new Error("useMotion must be used within a GsapProvider");
  }
  return context;
}
