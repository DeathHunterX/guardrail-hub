/**
 * Single source of truth for responsive breakpoints.
 * Imported by both `tailwind.config.ts` (CSS) and `use-media-query.ts` (JS)
 * so the two can never drift apart.
 */
export const screens = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  "2xl": 1536,
} as const;

export type Screen = keyof typeof screens;
