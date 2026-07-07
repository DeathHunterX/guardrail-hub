import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merges Tailwind classes with conflict resolution. The only sanctioned way to build conditional class strings. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
