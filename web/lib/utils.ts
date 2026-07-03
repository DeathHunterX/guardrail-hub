import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merges Tailwind classes with conflict resolution. The only sanctioned way to build conditional class strings. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const compactFormatter = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** Formats 24300 as "24.3K" — GitHub stars, stat chips. */
export function formatCompactNumber(value: number): string {
  return compactFormatter.format(value);
}
