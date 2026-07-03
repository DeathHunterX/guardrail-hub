/**
 * Motion tokens — the only source of animation timing values (spec §2.5).
 * Components must consume these constants; numeric literals in tweens are
 * rejected in review.
 */
export const durations = {
  /** Micro state changes: chips, dots, toggles. */
  xs: 0.2,
  /** Small reveals and hover-adjacent motion. */
  sm: 0.4,
  /** Default section reveal duration. */
  md: 0.6,
  /** Large panel arrivals. */
  lg: 0.9,
  /** Signature landings (hero workspace, dashboard window). */
  xl: 1.4,
} as const;

export const eases = {
  /** Default arrival ease. */
  enter: "power3.out",
  /** State changes and Flip morphs. */
  morph: "power2.inOut",
  /** Playful pops: chips, badges, featured pricing card. */
  pop: "back.out(1.4)",
  /** The two "wow" landings. */
  land: "expo.out",
  /** Marquees, orbits, particle loops. */
  linear: "none",
} as const;

export const staggers = {
  tight: 0.06,
  base: 0.1,
  loose: 0.15,
} as const;

/** Standard ScrollTrigger start position for one-shot section reveals. */
export const revealStart = "top 75%";

/**
 * Earlier start for compact (mobile/tablet) viewports: small screens scroll
 * whole viewports at a time, so a 75% trigger often fires after the section
 * is already being read and the reveal looks like content loading late.
 */
export const revealStartCompact = "top 92%";

/** Viewport fractions matching the reveal start strings above. */
export const revealStartFraction = 0.75;
export const revealStartFractionCompact = 0.92;

/**
 * Scroll velocity (px/s) above which one-shot reveals finish instantly:
 * a reader flinging past a section should never wait for a late tween.
 */
export const fastScrollVelocity = 2000;

/**
 * When the hero intro is allowed to play, it starts this many seconds after
 * page load — the completed SSR state stays readable, then the story runs.
 */
export const introStartAfterLoad = 3.2;

/**
 * Entrance intros should only replay over freshly painted content. When
 * hydration happens late (slow device/network) or the browser restored a
 * scroll position, the SSR final state has already been on screen — hiding
 * it again to replay the animation reads as a freeze-and-reset glitch.
 */
export function shouldPlayIntro(
  maxElapsedMs = 2500,
  maxScrollY = 80,
): boolean {
  if (typeof window === "undefined") return false;
  return window.scrollY <= maxScrollY && performance.now() <= maxElapsedMs;
}
